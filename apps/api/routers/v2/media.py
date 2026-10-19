"""
ShivAI V2.0 Free Multimodal Media Generation Router.
Provides endpoints for text-to-image, text-to-video, and neural speech generation.
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Response, Query, status
from pydantic import BaseModel, Field

from core.media.generator import media_generator

v2_media_router = APIRouter(prefix="/v2/media", tags=["v2 - Free Media Generation"])


class ImageRequest(BaseModel):
    prompt: str = Field(..., description="Description of the image to generate", json_schema_extra={"example": "Cyberpunk city with neon lights and flying cars, cinematic 8k"})
    width: Optional[int] = Field(1024, ge=256, le=2048, description="Image width in pixels")
    height: Optional[int] = Field(1024, ge=256, le=2048, description="Image height in pixels")
    model: Optional[str] = Field("flux", description="Model variant: 'flux', 'turbo', 'flux-realism', 'flux-anime'")
    seed: Optional[int] = Field(None, description="Optional random seed for reproducible results")


class VideoRequest(BaseModel):
    prompt: str = Field(..., description="Description of the video/animation to generate", json_schema_extra={"example": "A golden retriever puppy running on a tropical beach at sunset"})
    duration: Optional[int] = Field(3, ge=1, le=10, description="Duration in seconds")
    fps: Optional[int] = Field(16, ge=8, le=30, description="Frames per second")


class SpeechRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize into neural speech", json_schema_extra={"example": "नमस्ते, शिव एआई वी२ में आपका स्वागत है।"})
    voice: Optional[str] = Field("hi-IN-SwaraNeural", description="Voice identifier (e.g. 'hi-IN-SwaraNeural', 'en-IN-NeerjaNeural')")
    rate: Optional[str] = Field("+0%", description="Speaking speed adjustment (e.g. '+10%', '-10%')")
    pitch: Optional[str] = Field("+0Hz", description="Pitch adjustment")


class MusicRequest(BaseModel):
    prompt: str = Field(..., description="Prompt describing the instrumental style or sound effect", json_schema_extra={"example": "Upbeat ambient lo-fi beat with soft piano and rain sounds"})


@v2_media_router.post("/image", response_model=Dict[str, Any])
async def create_image(payload: ImageRequest):
    """Generates photorealistic images via serverless Flux/SDXL."""
    try:
        return await media_generator.generate_image(
            prompt=payload.prompt,
            width=payload.width or 1024,
            height=payload.height or 1024,
            model=payload.model or "flux",
            seed=payload.seed
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Image generation error: {str(e)}")


@v2_media_router.get("/image")
async def render_image(
    prompt: str = Query(..., description="Prompt to generate"),
    width: int = Query(1024, ge=256, le=2048),
    height: int = Query(1024, ge=256, le=2048),
    model: str = Query("flux")
):
    """Direct embeddable image endpoint returning image bytes."""
    try:
        res = await media_generator.generate_image(
            prompt=prompt,
            width=width,
            height=height,
            model=model,
            fetch_bytes=True
        )
        return Response(content=res["bytes"], media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@v2_media_router.post("/video", response_model=Dict[str, Any])
async def create_video(payload: VideoRequest):
    """Generates animated clips or short videos."""
    try:
        return await media_generator.generate_video(
            prompt=payload.prompt,
            duration_seconds=payload.duration or 3,
            fps=payload.fps or 16
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Video generation error: {str(e)}")


@v2_media_router.post("/speech")
async def create_speech(payload: SpeechRequest):
    """Generates neural speech MP3 audio."""
    try:
        audio_bytes = await media_generator.generate_speech(
            text=payload.text,
            voice=payload.voice or "hi-IN-SwaraNeural",
            rate=payload.rate or "+0%",
            pitch=payload.pitch or "+0Hz"
        )
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": 'inline; filename="speech.mp3"'}
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Speech synthesis error: {str(e)}")


@v2_media_router.get("/speech")
async def render_speech(
    text: str = Query(..., description="Text to speak"),
    voice: str = Query("hi-IN-SwaraNeural", description="Voice ID")
):
    """Direct embeddable audio stream endpoint."""
    try:
        audio_bytes = await media_generator.generate_speech(text=text, voice=voice)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": 'inline; filename="speech.mp3"'}
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@v2_media_router.post("/music")
async def create_music(payload: MusicRequest):
    """Generates short instrumental audio via MusicGen."""
    try:
        music_bytes = await media_generator.generate_music(prompt=payload.prompt)
        return Response(
            content=music_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": 'inline; filename="music.wav"'}
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Music generation error: {str(e)}")
