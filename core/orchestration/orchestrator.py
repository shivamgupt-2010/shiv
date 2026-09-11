"""
ShivAI Master AI Orchestrator.
Coordinates intent classification, context building, model routing,
fault-tolerant execution, persistence, and unified response delivery.
"""
import logging
from typing import Dict, Any, Optional, AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from core.orchestration.task_classifier import TaskClassifier
from core.agents.agent_manager import agent_manager
from core.memory.memory_manager import MemoryManager
from core.context.context_builder import context_builder
from core.routing.router import model_router
from core.routing.fallback_handler import FallbackHandler
from database.repositories.conversation_repo import ConversationRepository
from providers.base import UnifiedResponse, UnifiedStreamChunk

logger = logging.getLogger("shivai.orchestrator")


class ShivAIOrchestrator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.conv_repo = ConversationRepository(session)
        self.memory_mgr = MemoryManager(session)
        self.fallback_handler = FallbackHandler(session)

    async def process_chat(
        self,
        user_message: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> UnifiedResponse:
        """
        Executes a complete non-streaming chat turn with persistent conversation and memory.
        """
        req_id = request_id or "req-default"

        # 1. Ensure conversation exists
        conversation = await self.conv_repo.get_or_create(
            conversation_id=conversation_id,
            user_id=user_id,
            title=user_message[:50] + "..." if len(user_message) > 50 else user_message,
        )

        # 2. Record incoming user message
        await self.conv_repo.add_message(
            conversation_id=conversation.id,
            role="user",
            content=user_message,
        )

        # 3. Task & Capability analysis
        task_type, auto_caps = TaskClassifier.classify(user_message)
        agent_key = agent_name or task_type
        agent = agent_manager.get_agent(agent_key)
        required_caps = {**auto_caps, **agent.required_capabilities}

        # 4. Context & Memory retrieval
        memories = await self.memory_mgr.recall(user_id=user_id, query=user_message)
        history = await self.conv_repo.get_recent_messages(conversation_id=conversation.id, limit=20)

        # 5. Model Candidate Ranking
        candidates = await model_router.get_ranked_candidates(
            session=self.session,
            required_capabilities=required_caps,
            preferred_provider=preferred_provider,
        )

        # 6. Context construction
        # Target largest candidate context or default
        target_context = candidates[0].context_limit if candidates else 32000
        assembled_messages = context_builder.build_context(
            user_message=user_message,
            conversation_history=history[:-1] if history else [],  # exclude just-saved user message to avoid duplicate
            memories=memories,
            agent_instructions=agent.instructions,
            custom_instructions=custom_instructions or conversation.system_instruction_override,
            context_limit=target_context,
        )

        # 7. Fault-tolerant execution across models
        response = await self.fallback_handler.execute_with_fallback(
            candidates=candidates,
            messages=assembled_messages,
            options=options,
            request_id=req_id,
            user_id=user_id,
            conversation_id=conversation.id,
        )

        # 8. Record assistant response in conversation
        await self.conv_repo.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content=response.content,
            model_provider=response.model.provider,
            model_name=response.model.model,
            tokens_input=response.usage.input_tokens,
            tokens_output=response.usage.output_tokens,
            finish_reason=response.finish_reason,
        )

        # Attach conversation ID to response metadata
        response.metadata["conversation_id"] = conversation.id
        return response

    async def process_chat_stream(
        self,
        user_message: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> AsyncIterator[UnifiedStreamChunk]:
        """
        Executes a streaming chat turn with chunk normalization and fallback.
        """
        req_id = request_id or "req-default"

        conversation = await self.conv_repo.get_or_create(
            conversation_id=conversation_id,
            user_id=user_id,
            title=user_message[:50] + "..." if len(user_message) > 50 else user_message,
        )

        await self.conv_repo.add_message(
            conversation_id=conversation.id,
            role="user",
            content=user_message,
        )

        task_type, auto_caps = TaskClassifier.classify(user_message)
        agent = agent_manager.get_agent(agent_name or task_type)
        required_caps = {**auto_caps, **agent.required_capabilities, "streaming": True}

        memories = await self.memory_mgr.recall(user_id=user_id, query=user_message)
        history = await self.conv_repo.get_recent_messages(conversation_id=conversation.id, limit=20)

        candidates = await model_router.get_ranked_candidates(
            session=self.session,
            required_capabilities=required_caps,
            preferred_provider=preferred_provider,
        )

        target_context = candidates[0].context_limit if candidates else 32000
        assembled_messages = context_builder.build_context(
            user_message=user_message,
            conversation_history=history[:-1] if history else [],
            memories=memories,
            agent_instructions=agent.instructions,
            custom_instructions=custom_instructions or conversation.system_instruction_override,
            context_limit=target_context,
        )

        stream_gen = self.fallback_handler.stream_with_fallback(
            candidates=candidates,
            messages=assembled_messages,
            options=options,
            request_id=req_id,
            user_id=user_id,
            conversation_id=conversation.id,
        )

        full_content = []
        selected_provider = None
        selected_model = None

        async for chunk in stream_gen:
            if chunk.delta:
                full_content.append(chunk.delta)
            if chunk.model:
                selected_provider = chunk.model.provider
                selected_model = chunk.model.model
            yield chunk

        # Save assistant message upon stream completion
        assembled_text = "".join(full_content)
        if assembled_text:
            await self.conv_repo.add_message(
                conversation_id=conversation.id,
                role="assistant",
                content=assembled_text,
                model_provider=selected_provider,
                model_name=selected_model,
            )
            await self.session.commit()
