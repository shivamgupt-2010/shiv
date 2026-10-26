"""
ShivAI V2 Voice AI Endpoints.
Provides:
- POST /v2/voice/stt: Low-latency speech-to-text (Groq Whisper)
- POST /v2/voice/tts: Streaming neural speech synthesis (Edge-TTS)
- WebSocket /v2/voice/stream: Full-duplex conversational voice loop with barge-in support
"""
import json
import time
import logging
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from apps.api.dependencies import get_current_user_context, UserContext, rate_limit_middleware_check
from core.voice.stt import stt_engine
from core.voice.tts import tts_engine
from core.voice.session import voice_session_registry, VoiceState
from core.v2.request_service import V2RequestService, V2ChatRequest

logger = logging.getLogger("shivai.api.v2.voice")

router = APIRouter(tags=["V2 Voice AI"])


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Text to synthesize")
    voice: Optional[str] = Field(default=None, description="Voice preset: hindi_female, hindi_male, english_female, english_male")
    rate: Optional[str] = Field(default="+0%", description="Speaking speed adjustment (e.g. +10%, -10%)")
    pitch: Optional[str] = Field(default="+0Hz", description="Voice pitch adjustment")


@router.post(
    "/v2/voice/stt",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.post(
    "/api/v2/voice/stt",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def voice_transcribe(
    file: UploadFile = File(..., description="Audio file in WAV, MP3, or OGG format"),
    language: Optional[str] = Form(default=None, description="Optional ISO language code (e.g. 'hi' for Hindi, 'en' for English)"),
    user: UserContext = Depends(get_current_user_context),
):
    """
    Transcribes spoken audio into text with high accuracy across Hindi, English, and Hinglish.
    Uses Groq Whisper API for sub-300ms transcription latency.
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        return JSONResponse(status_code=400, content={"error": {"code": "EMPTY_AUDIO", "message": "Uploaded audio file is empty."}})

    result = await stt_engine.transcribe(
        audio_bytes=audio_bytes,
        filename=file.filename or "audio.wav",
        language=language,
    )
    return result.to_dict()


@router.post(
    "/v2/voice/tts",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.post(
    "/api/v2/voice/tts",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def voice_synthesize(
    req: TTSRequest,
    user: UserContext = Depends(get_current_user_context),
):
    """
    Synthesizes text into high-fidelity streaming neural speech (MP3).
    Zero API key required, native human Hindi and Indian English pronunciation.
    """
    generator = tts_engine.synthesize_stream(
        text=req.text,
        voice=req.voice,
        rate=req.rate or "+0%",
        pitch=req.pitch or "+0Hz",
    )

    return StreamingResponse(
        generator,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Content-Disposition": 'inline; filename="speech.mp3"',
            "X-Voice-Engine": "ShivAI-Neural-EdgeTTS",
        },
    )


@router.websocket("/v2/voice/stream")
async def voice_websocket_stream(websocket: WebSocket):
    """
    Full-duplex real-time voice streaming WebSocket.
    Supports continuous conversation, early sentence playback, and immediate barge-in interruption.
    """
    await websocket.accept()
    session_id = f"voice_ws_{int(time.time() * 1000)}"
    user_id = "ws_user"
    session = voice_session_registry.get_or_create(session_id, user_id)

    logger.info(f"[{session_id}] Voice WebSocket connected.")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "barge_in" or msg_type == "interrupt":
                # User interrupted speech
                session.trigger_barge_in()
                await websocket.send_json({"type": "interrupted", "session_id": session_id})
                continue

            elif msg_type == "text_query":
                # Text query input with streaming voice output
                user_query = message.get("text", "")
                if user_query:
                    # Let V2 request service process
                    service = V2RequestService()
                    chat_req = V2ChatRequest(message=user_query, mode="fastest")
                    chat_res = await service.execute_chat(chat_req, user_id=user_id, request_id=f"ws-{int(time.time())}")
                    
                    # Stream text transcript
                    await websocket.send_json({
                        "type": "transcript",
                        "text": chat_res.response,
                        "provider": chat_res.provider,
                        "model": chat_res.model,
                    })

                    # Stream synthesized audio chunks
                    async for audio_chunk in session.stream_spoken_response(chat_res.response):
                        await websocket.send_bytes(audio_chunk)

                    await websocket.send_json({"type": "turn_completed"})

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"[{session_id}] Voice WebSocket disconnected.")
    except Exception as e:
        logger.error(f"[{session_id}] Voice WebSocket exception: {e}")
    finally:
        voice_session_registry.remove(session_id)
