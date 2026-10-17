"""
ShivAI V2 Chat & Streaming Endpoints.
Exposes POST /v2/chat and POST /v2/chat/stream with Server-Sent Events (SSE).
"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, status, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db, get_current_user_context, UserContext, get_request_id, rate_limit_middleware_check
from core.v2.request_service import V2RequestService, V2ChatRequest, V2ChatResponse
from providers.errors import ProviderError

logger = logging.getLogger("shivai.api.v2.chat")

router = APIRouter(tags=["V2 Chat & Inference"])


@router.post(
    "/v2/chat",
    response_model=V2ChatResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.post(
    "/api/v2/chat",
    response_model=V2ChatResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def v2_chat_completion(
    req: V2ChatRequest,
    user: UserContext = Depends(get_current_user_context),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_db),
) -> V2ChatResponse:
    """
    V2 Standard Chat Completion:
    Executes an intelligent multi-provider turn with circuit breakers, auto-rotation, and structured outputs.
    """
    service = V2RequestService(session)
    try:
        return await service.execute_chat(
            request=req,
            user_id=user.user_id,
            request_id=request_id,
        )
    except ProviderError as pe:
        logger.warning(f"[{request_id}] V2 Provider Error: {pe.to_dict()}")
        return JSONResponse(
            status_code=pe.status_code or status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": pe.category.value,
                    "message": pe.message,
                    "provider": pe.provider,
                    "request_id": request_id,
                }
            },
        )
    except Exception as e:
        logger.exception(f"[{request_id}] V2 Chat unexpected failure: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"ShivAI server error: {str(e)}",
                    "request_id": request_id,
                }
            },
        )


@router.post(
    "/v2/chat/stream",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.post(
    "/api/v2/chat/stream",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def v2_chat_stream(
    req: V2ChatRequest,
    request: Request,
    user: UserContext = Depends(get_current_user_context),
    request_id: str = Depends(get_request_id),
    session: AsyncSession = Depends(get_db),
):
    """
    V2 Server-Sent Events (SSE) Streaming:
    Streams token chunks progressively to the client with graceful client disconnect handling.
    """
    service = V2RequestService(session)

    async def event_generator():
        try:
            stream_iter = service.execute_stream(
                request=req,
                user_id=user.user_id,
                request_id=request_id,
            )
            async for chunk in stream_iter:
                if await request.is_disconnected():
                    logger.info(f"[{request_id}] Client disconnected during SSE streaming.")
                    break

                if chunk.delta:
                    payload = {"type": "token", "content": chunk.delta, "request_id": request_id}
                    yield f"data: {json.dumps(payload)}\n\n"

            # Emit clean done signal
            yield f"data: {json.dumps({'type': 'done', 'request_id': request_id})}\n\n"
        except ProviderError as pe:
            err_data = {
                "type": "error",
                "error": {
                    "code": pe.category.value,
                    "message": pe.message,
                    "request_id": request_id,
                }
            }
            yield f"data: {json.dumps(err_data)}\n\n"
        except Exception as exc:
            logger.exception(f"[{request_id}] Streaming error: {exc}")
            err_data = {
                "type": "error",
                "error": {
                    "code": "STREAM_ERROR",
                    "message": str(exc),
                    "request_id": request_id,
                }
            }
            yield f"data: {json.dumps(err_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )
