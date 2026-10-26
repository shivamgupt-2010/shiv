"""
ShivAI V2 Core Request Service.
Decouples API layer from external AI providers.
Coordinates:
- Intelligent Model Routing (auto, fastest, quality, balanced, specific)
- Hierarchical Memory & Context Building
- Circuit Breaker & Asynchronous Retry Engine
- Structured Output validation (JSON Schema)
- Unified SSE Streaming Generator
"""
import json
import time
import re
import logging
from typing import Dict, Any, Optional, List, AsyncIterator
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from providers.registry import provider_registry
from providers.base import UnifiedResponse, UnifiedStreamChunk
from providers.errors import ProviderError, ErrorCategory
from core.routing.router import model_router, RoutingDecision
from core.routing.scoring import RoutingMode
from core.routing.registry import ModelInfo
from core.resilience.circuit_breaker import circuit_breaker_registry
from core.resilience.retry import execute_with_retry
from core.resilience.key_pool import key_pool_manager
from core.memory.service import HierarchicalMemoryService
from core.multilingual.language import language_engine
from database.repositories.conversation_repo import ConversationRepository

logger = logging.getLogger("shivai.v2.request_service")


class V2ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=50000, description="The user's query or prompt")
    conversation_id: Optional[str] = Field(default=None, description="Optional existing conversation ID")
    mode: str = Field(default="auto", description="Routing mode: auto, fastest, quality, balanced, specific")
    model: Optional[str] = Field(default=None, description="Explicit model name (used when mode=specific)")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=4096, ge=1, le=32768)
    response_format: Optional[Dict[str, Any]] = Field(default=None, description="Optional JSON Schema or json_object format")


class V2UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class V2ChatResponse(BaseModel):
    response: str
    conversation_id: str
    provider: str
    model: str
    request_id: str
    usage: V2UsageInfo = Field(default_factory=V2UsageInfo)
    structured_data: Optional[Any] = None
    latency_ms: float = 0.0


def extract_and_validate_json(raw_text: str, schema: Optional[Dict[str, Any]] = None) -> Any:
    """
    Cleans markdown code fences and parses JSON.
    Validates structure if schema is provided.
    """
    cleaned = raw_text.strip()
    # Strip markdown fences ```json ... ```
    if cleaned.startswith("```"):
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as err:
        raise ProviderError(
            category=ErrorCategory.BAD_REQUEST,
            message=f"Model output could not be parsed as valid JSON: {err}",
            provider="validator",
            raw_error=raw_text,
        )

    # Basic schema validation if required fields specified
    if schema and isinstance(schema, dict) and isinstance(parsed, dict):
        required_fields = schema.get("required", [])
        missing = [f for f in required_fields if f not in parsed]
        if missing:
            raise ProviderError(
                category=ErrorCategory.BAD_REQUEST,
                message=f"Model JSON output missing required schema fields: {missing}",
                provider="validator",
                raw_error=raw_text,
            )

    return parsed


class V2RequestService:
    """Orchestrates V2 chat turns, intelligent routing, and resilience."""

    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
        self.conv_repo = ConversationRepository(session) if session else None
        self.memory_service = HierarchicalMemoryService(session) if session else None

    async def execute_chat(
        self,
        request: V2ChatRequest,
        user_id: str,
        request_id: str,
    ) -> V2ChatResponse:
        """Executes a complete non-streaming chat completion with intelligent routing & fallback."""
        start_time = time.perf_counter()

        # 1. Ensure conversation exists in DB
        conversation_id = request.conversation_id
        if self.conv_repo:
            conv = await self.conv_repo.get_or_create(
                conversation_id=conversation_id,
                user_id=user_id,
                title=request.message[:50] + "..." if len(request.message) > 50 else request.message,
            )
            conversation_id = conv.id
            # Record user message
            await self.conv_repo.add_message(
                conversation_id=conversation_id,
                role="user",
                content=request.message,
            )
        else:
            conversation_id = conversation_id or f"conv_{int(time.time())}"

        # 2. Assemble hierarchical memory context & language directives
        lang_directive = language_engine.get_system_prompt_instruction(request.message)
        system_instruction = f"You are ShivAI, an intelligent, resilient, autonomous AI assistant.\n{lang_directive}"
        messages: List[Dict[str, Any]] = []

        if self.memory_service:
            context_data = await self.memory_service.get_hierarchical_context(
                user_id=user_id,
                conversation_id=conversation_id,
                query=request.message,
            )
            memory_prompt = self.memory_service.format_context_for_prompt(context_data)
            if memory_prompt:
                system_instruction += f"\n\n{memory_prompt}"

            # Add recent conversation turns
            history = context_data.get("conversation_history", [])
            messages.append({"role": "system", "content": system_instruction})
            for h in history[:-1]:  # exclude just-added message
                messages.append({"role": h.role, "content": h.content})
        else:
            messages.append({"role": "system", "content": system_instruction})

        messages.append({"role": "user", "content": request.message})

        # 3. Route to optimal model
        required_caps = {}
        if request.response_format:
            required_caps["structured_output"] = True

        decision = await model_router.route_request(
            mode=request.mode,
            specific_model_name=request.model,
            required_capabilities=required_caps,
            session=self.session,
        )

        candidates = decision.ranked_candidates
        options = {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "response_format": request.response_format,
        }

        # 4. Fallback execution across candidates
        last_error = None
        for candidate in candidates:
            provider = provider_registry.get_provider(candidate.provider)
            if not provider:
                continue

            breaker = await circuit_breaker_registry.get_or_create(candidate.provider)
            if not await breaker.can_execute():
                logger.info(f"[{request_id}] Skipping '{candidate.model_id}' due to OPEN circuit breaker.")
                continue

            try:
                # Execute with retry
                async def _call():
                    return await provider.generate(
                        model=candidate.model_name,
                        messages=messages,
                        options=options,
                        request_id=request_id,
                    )

                unified_resp: UnifiedResponse = await execute_with_retry(
                    operation=_call,
                    operation_name=f"{candidate.provider}:{candidate.model_name}",
                )

                # Record success on circuit breaker
                await breaker.record_success()

                # Process Structured Output if requested
                structured_data = None
                if request.response_format:
                    schema_to_check = request.response_format.get("schema")
                    if not schema_to_check and "json_schema" in request.response_format:
                        schema_to_check = request.response_format["json_schema"].get("schema")
                    structured_data = extract_and_validate_json(unified_resp.content, schema_to_check)

                latency_ms = (time.perf_counter() - start_time) * 1000.0

                # 5. Persist assistant response
                if self.conv_repo:
                    await self.conv_repo.add_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=unified_resp.content,
                        model_provider=candidate.provider,
                        model_name=candidate.model_name,
                        tokens_input=unified_resp.usage.input_tokens,
                        tokens_output=unified_resp.usage.output_tokens,
                    )
                    await self.session.commit()

                return V2ChatResponse(
                    response=unified_resp.content,
                    conversation_id=conversation_id,
                    provider=candidate.provider,
                    model=candidate.model_name,
                    request_id=request_id,
                    usage=V2UsageInfo(
                        input_tokens=unified_resp.usage.input_tokens,
                        output_tokens=unified_resp.usage.output_tokens,
                        total_tokens=unified_resp.usage.total_tokens,
                    ),
                    structured_data=structured_data,
                    latency_ms=round(latency_ms, 2),
                )
            except Exception as exc:
                last_error = exc
                await breaker.record_failure(str(exc))
                logger.warning(
                    f"[{request_id}] Candidate '{candidate.model_id}' failed: {exc}. "
                    f"Attempting fallback to next eligible model..."
                )
                if decision.mode == RoutingMode.SPECIFIC:
                    # In SPECIFIC mode, do not silently switch models
                    raise exc

        raise last_error or ProviderError(
            category=ErrorCategory.SERVER_ERROR,
            message="All candidate models failed to produce a response.",
            provider="router",
            status_code=503,
        )

    async def execute_stream(
        self,
        request: V2ChatRequest,
        user_id: str,
        request_id: str,
    ) -> AsyncIterator[UnifiedStreamChunk]:
        """Executes a streaming chat turn yielding chunks."""
        # 1. Setup conversation
        conversation_id = request.conversation_id
        if self.conv_repo:
            conv = await self.conv_repo.get_or_create(
                conversation_id=conversation_id,
                user_id=user_id,
                title=request.message[:50] + "..." if len(request.message) > 50 else request.message,
            )
            conversation_id = conv.id
            await self.conv_repo.add_message(
                conversation_id=conversation_id,
                role="user",
                content=request.message,
            )
        else:
            conversation_id = conversation_id or f"conv_{int(time.time())}"

        # 2. Build context with language directives
        lang_directive = language_engine.get_system_prompt_instruction(request.message)
        system_instruction = f"You are ShivAI, an intelligent, resilient, autonomous AI assistant.\n{lang_directive}"
        messages: List[Dict[str, Any]] = []

        if self.memory_service:
            context_data = await self.memory_service.get_hierarchical_context(
                user_id=user_id,
                conversation_id=conversation_id,
                query=request.message,
            )
            memory_prompt = self.memory_service.format_context_for_prompt(context_data)
            if memory_prompt:
                system_instruction += f"\n\n{memory_prompt}"

            history = context_data.get("conversation_history", [])
            messages.append({"role": "system", "content": system_instruction})
            for h in history[:-1]:
                messages.append({"role": h.role, "content": h.content})
        else:
            messages.append({"role": "system", "content": system_instruction})

        messages.append({"role": "user", "content": request.message})

        # 3. Route
        decision = await model_router.route_request(
            mode=request.mode,
            specific_model_name=request.model,
            required_capabilities={"streaming": True},
            session=self.session,
        )

        candidates = decision.ranked_candidates
        options = {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        # 4. Stream with fallback across candidates
        stream_succeeded = False
        full_response_text: List[str] = []
        chosen_provider = None
        chosen_model = None

        for candidate in candidates:
            provider = provider_registry.get_provider(candidate.provider)
            if not provider:
                continue

            breaker = await circuit_breaker_registry.get_or_create(candidate.provider)
            if not await breaker.can_execute():
                continue

            try:
                stream_iter = provider.stream(
                    model=candidate.model_name,
                    messages=messages,
                    options=options,
                    request_id=request_id,
                )
                async for chunk in stream_iter:
                    if chunk.delta:
                        full_response_text.append(chunk.delta)
                    yield chunk

                stream_succeeded = True
                chosen_provider = candidate.provider
                chosen_model = candidate.model_name
                await breaker.record_success()
                break
            except Exception as stream_err:
                await breaker.record_failure(str(stream_err))
                logger.warning(f"[{request_id}] Streaming candidate '{candidate.model_id}' failed: {stream_err}")
                if decision.mode == RoutingMode.SPECIFIC:
                    raise stream_err

        if not stream_succeeded:
            raise ProviderError(
                category=ErrorCategory.SERVER_ERROR,
                message="All streaming candidate models failed to stream response.",
                provider="router",
                status_code=503,
            )

        # 5. Persist complete streamed assistant turn
        if self.conv_repo and full_response_text:
            assembled = "".join(full_response_text)
            try:
                await self.conv_repo.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assembled,
                    model_provider=chosen_provider,
                    model_name=chosen_model,
                )
                await self.session.commit()
            except Exception as db_err:
                logger.warning(f"Failed to record streamed message: {db_err}")
