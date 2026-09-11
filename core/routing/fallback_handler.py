"""
Automatic Fallback & Resilience Handler.
Executes AI requests across ranked candidate models with error classification,
provider status persistence, and transparent multi-provider failover.
"""
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from core.routing.router import ModelConfig
from providers.base import UnifiedResponse, UnifiedStreamChunk
from providers.registry import provider_registry
from providers.errors import ProviderError, ErrorCategory
from database.repositories.provider_repo import ProviderRepository
from database.repositories.usage_repo import UsageRepository

logger = logging.getLogger("shivai.fallback")


class ShivAIServiceException(Exception):
    """Clean user-facing exception when all AI providers are exhausted."""

    def __init__(self, message: str, request_id: str, code: str = "AI_SERVICE_TEMPORARILY_UNAVAILABLE"):
        super().__init__(message)
        self.message = message
        self.request_id = request_id
        self.code = code

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": self.request_id,
            }
        }


class FallbackHandler:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.provider_repo = ProviderRepository(session)
        self.usage_repo = UsageRepository(session)

    async def execute_with_fallback(
        self,
        candidates: List[ModelConfig],
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> UnifiedResponse:
        """
        Executes a non-streaming completion across candidate models until success.
        """
        req_id = request_id or "req-default"
        if not candidates:
            raise ShivAIServiceException(
                message="No AI model providers are currently configured or available.",
                request_id=req_id,
                code="NO_PROVIDERS_AVAILABLE",
            )

        last_error: Optional[ProviderError] = None

        for idx, candidate in enumerate(candidates):
            provider = provider_registry.get_provider(candidate.provider)
            logger.info(
                f"[{req_id}] Attempting provider '{candidate.provider}' model '{candidate.model}' (candidate {idx + 1}/{len(candidates)})"
            )

            try:
                response = await provider.generate(
                    model=candidate.model,
                    messages=messages,
                    options=options,
                    request_id=req_id,
                )

                # Record success & usage
                await self.provider_repo.record_success(candidate.provider)
                await self.usage_repo.record_usage(
                    request_id=req_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    provider=candidate.provider,
                    model=candidate.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    latency_ms=response.latency_ms,
                    status="success",
                )
                return response

            except Exception as exc:
                normalized = provider.normalize_error(exc, model=candidate.model)
                last_error = normalized

                logger.warning(
                    f"[{req_id}] Provider '{candidate.provider}' failed with {normalized.category.value}: {normalized.message}"
                )

                # Persist health failure status & apply appropriate cooldown
                cooldown = 60
                if normalized.category in (ErrorCategory.QUOTA_EXCEEDED, ErrorCategory.INSUFFICIENT_CREDITS):
                    cooldown = 900  # 15 min cooldown for quota exhaustion
                elif normalized.category == ErrorCategory.RATE_LIMIT:
                    cooldown = normalized.retry_after or 45
                elif normalized.category == ErrorCategory.AUTH_ERROR:
                    cooldown = 3600  # 1 hour cooldown for auth failure

                await self.provider_repo.record_failure(
                    provider=candidate.provider,
                    error_category=normalized.category.value,
                    error_message=normalized.message,
                    cooldown_seconds=cooldown,
                )
                await self.usage_repo.record_usage(
                    request_id=req_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    provider=candidate.provider,
                    model=candidate.model,
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=0.0,
                    status="fallback",
                    error_category=normalized.category.value,
                )

                # Continue loop to next candidate
                continue

        # All candidates exhausted
        error_detail = last_error.message if last_error else "All candidate providers failed."
        raise ShivAIServiceException(
            message=f"ShivAI could not complete the request right now: {error_detail}",
            request_id=req_id,
        )

    async def stream_with_fallback(
        self,
        candidates: List[ModelConfig],
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> AsyncIterator[UnifiedStreamChunk]:
        """
        Executes streaming completion. If provider fails before yielding chunks,
        seamlessly falls back to the next candidate.
        """
        req_id = request_id or "req-default"
        if not candidates:
            raise ShivAIServiceException(
                message="No AI model providers are currently configured or available.",
                request_id=req_id,
                code="NO_PROVIDERS_AVAILABLE",
            )

        last_error = None

        for idx, candidate in enumerate(candidates):
            provider = provider_registry.get_provider(candidate.provider)
            logger.info(
                f"[{req_id}] Streaming attempt with '{candidate.provider}' model '{candidate.model}'"
            )

            chunks_emitted = 0
            try:
                stream_iter = provider.stream(
                    model=candidate.model,
                    messages=messages,
                    options=options,
                    request_id=req_id,
                )

                async for chunk in stream_iter:
                    chunks_emitted += 1
                    yield chunk

                # If completed without exception, record success
                await self.provider_repo.record_success(candidate.provider)
                return

            except Exception as exc:
                normalized = provider.normalize_error(exc, model=candidate.model)
                last_error = normalized

                logger.warning(
                    f"[{req_id}] Streaming provider '{candidate.provider}' failed: {normalized.message}"
                )

                await self.provider_repo.record_failure(
                    provider=candidate.provider,
                    error_category=normalized.category.value,
                    error_message=normalized.message,
                    cooldown_seconds=60,
                )

                # If tokens were already emitted to client, we cannot cleanly restart the stream
                if chunks_emitted > 0:
                    yield UnifiedStreamChunk(
                        request_id=req_id,
                        assistant="shivai",
                        delta="\n\n[Connection to model interrupted. Streaming terminated.]",
                        finish_reason="error",
                    )
                    return

                # If 0 chunks emitted, fall back to next candidate!
                continue

        # All candidates failed
        raise ShivAIServiceException(
            message="ShivAI could not complete the stream right now.",
            request_id=req_id,
        )
