"""
Chat endpoints supporting non-streaming and Server-Sent Events (SSE) streaming.
"""
import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.dependencies import get_db, get_current_user_id, get_request_id, rate_limit_middleware_check
from core.orchestration.orchestrator import ShivAIOrchestrator
from providers.base import UnifiedResponse

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=50000, description="The user's query or prompt")
    conversation_id: Optional[str] = Field(default=None, description="Optional existing conversation ID")
    agent: Optional[str] = Field(default=None, description="Optional agent persona (coding, math, research, general)")
    custom_instructions: Optional[str] = Field(default=None, description="Temporary task instructions")
    preferred_provider: Optional[str] = Field(default=None, description="Optional preferred AI provider")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=4096, ge=1, le=16384)


@router.post(
    "",
    response_model=UnifiedResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def chat_completion(
    req: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_db),
) -> UnifiedResponse:
    """
    Submits a message to ShivAI and returns a unified response.
    Under the hood, ShivAI selects, rotates, and falls back across all available models.
    """
    orchestrator = ShivAIOrchestrator(session)
    options = {
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
    }
    return await orchestrator.process_chat(
        user_message=req.message,
        user_id=user_id,
        conversation_id=req.conversation_id,
        agent_name=req.agent,
        custom_instructions=req.custom_instructions,
        preferred_provider=req.preferred_provider,
        options=options,
        request_id=request_id,
    )


@router.post(
    "/stream",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def chat_stream(
    req: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_db),
):
    """
    Streams ShivAI's response progressively via Server-Sent Events (SSE).
    """
    orchestrator = ShivAIOrchestrator(session)
    options = {
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
    }

    async def event_generator():
        try:
            stream_iter = orchestrator.process_chat_stream(
                user_message=req.message,
                user_id=user_id,
                conversation_id=req.conversation_id,
                agent_name=req.agent,
                custom_instructions=req.custom_instructions,
                preferred_provider=req.preferred_provider,
                options=options,
                request_id=request_id,
            )
            async for chunk in stream_iter:
                data = chunk.model_dump(mode="json")
                yield f"data: {json.dumps(data)}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            err_data = {"error": {"code": "STREAM_ERROR", "message": str(e), "request_id": request_id}}
            yield f"data: {json.dumps(err_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
