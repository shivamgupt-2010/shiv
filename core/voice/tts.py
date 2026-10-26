"""
ShivAI Neural Text-to-Speech (TTS) Subsystem.
Implements ultra-natural speech synthesis using Microsoft Edge Neural Voices.
100% free, zero API key required, low memory footprint (<20MB RAM, Render Free compatible).
Native Hindi (hi-IN-SwaraNeural, hi-IN-MadhurNeural) & Indian English/Hinglish (en-IN-NeerjaNeural, en-IN-PrabhatNeural).
"""
import re
import io
import asyncio
import logging
from typing import AsyncIterator, Optional, List, Dict, Any

logger = logging.getLogger("shivai.voice.tts")

# Voice presets
VOICE_MAP = {
    "hindi_female": "hi-IN-SwaraNeural",
    "hindi_male": "hi-IN-MadhurNeural",
    "english_female": "en-IN-NeerjaNeural",
    "english_male": "en-IN-PrabhatNeural",
    "default": "hi-IN-SwaraNeural",
}


def detect_voice_for_text(text: str, preferred_voice: Optional[str] = None) -> str:
    """Selects the best natural voice based on user preference or language script."""
    if preferred_voice:
        if preferred_voice in VOICE_MAP:
            return VOICE_MAP[preferred_voice]
        return preferred_voice

    # Check for Devanagari Unicode block (Hindi script: \u0900-\u097F)
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", text))
    if has_devanagari:
        return VOICE_MAP["hindi_female"]

    # For English / Romanized Hinglish, Indian English neural voice sounds most natural
    return VOICE_MAP["english_female"]


def split_into_speech_segments(text: str) -> List[str]:
    """
    Decomposes text into natural sentences/clauses for early audio synthesis.
    Enables instant playback while subsequent sentences are being generated.
    """
    clean = re.sub(r"```[\s\S]*?```", "[code block omitted]", text)  # Avoid reading raw code blocks
    clean = re.sub(r"[*_#`]", "", clean)                             # Strip markdown formatting
    # Split on sentence boundaries (. ! ? । \n)
    segments = re.split(r"(?<=[.!?।\n])\s+", clean)
    return [s.strip() for s in segments if s.strip()]


class NeuralEdgeTTS:
    """Streams audio chunks using edge_tts neural models."""

    def __init__(self, default_voice: str = "hi-IN-SwaraNeural"):
        self.default_voice = default_voice

    async def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> AsyncIterator[bytes]:
        """
        Synthesizes text into streaming MP3 audio chunks.
        """
        chosen_voice = detect_voice_for_text(text, preferred_voice=voice or self.default_voice)
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text=text, voice=chosen_voice, rate=rate, pitch=pitch)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        except ImportError:
            logger.warning("edge-tts library not yet loaded. Yielding silent header fallback.")
            yield b""
        except Exception as e:
            logger.error(f"TTS synthesis error for voice '{chosen_voice}': {e}")
            yield b""

    async def synthesize_bytes(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> bytes:
        """Synthesizes text into a complete MP3 audio byte buffer."""
        buf = io.BytesIO()
        async for chunk in self.synthesize_stream(text=text, voice=voice):
            buf.write(chunk)
        return buf.getvalue()


# Global TTS instance
tts_engine = NeuralEdgeTTS()
