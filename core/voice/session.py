"""
ShivAI Real-Time Voice Session Manager.
Coordinates:
- Speech state transitions (IDLE, WAKE_WORD_LISTENING, CAPTURING_COMMAND, PROCESSING, SPEAKING, INTERRUPTED)
- Sentence-by-sentence streaming TTS synthesis for instant playback
- Full-duplex barge-in: immediately stops AI speech when user speaks
"""
import time
import asyncio
import logging
from enum import Enum
from typing import Optional, Dict, Any, AsyncIterator, Callable, List
from core.voice.stt import stt_engine, STTResult
from core.voice.tts import tts_engine, split_into_speech_segments
from core.voice.vad import VoiceActivityDetector

logger = logging.getLogger("shivai.voice.session")


class VoiceState(str, Enum):
    IDLE = "IDLE"
    WAKE_WORD_LISTENING = "WAKE_WORD_LISTENING"
    CAPTURING_COMMAND = "CAPTURING_COMMAND"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"


class VoiceSession:
    """Manages an active real-time voice interaction turn."""

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.state: VoiceState = VoiceState.IDLE
        self.vad = VoiceActivityDetector()
        self._current_speech_task: Optional[asyncio.Task] = None
        self._is_interrupted = False
        self.transcript_history: List[Dict[str, str]] = []

    def set_state(self, new_state: VoiceState) -> None:
        logger.info(f"[{self.session_id}] Voice state: {self.state.value} -> {new_state.value}")
        self.state = new_state

    def trigger_barge_in(self) -> None:
        """Immediately stops ongoing AI speech playback and generation."""
        if self.state == VoiceState.SPEAKING:
            logger.info(f"[{self.session_id}] Barge-in detected! User interrupted ongoing speech.")
            self._is_interrupted = True
            if self._current_speech_task and not self._current_speech_task.done():
                self._current_speech_task.cancel()
            self.set_state(VoiceState.INTERRUPTED)

    async def process_user_audio(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
    ) -> STTResult:
        """Transcribes incoming user command."""
        self.set_state(VoiceState.PROCESSING)
        self._is_interrupted = False
        res = await stt_engine.transcribe(audio_bytes=audio_bytes, language=language)
        if res.text:
            self.transcript_history.append({"role": "user", "text": res.text})
        return res

    async def stream_spoken_response(
        self,
        full_text: str,
        voice: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """
        Segments the text into complete sentences and streams synthesized MP3 chunks.
        Yields immediately per segment to achieve ultra-low first-audio latency.
        """
        self.set_state(VoiceState.SPEAKING)
        self.transcript_history.append({"role": "assistant", "text": full_text})
        segments = split_into_speech_segments(full_text)

        for segment in segments:
            if self._is_interrupted:
                logger.info(f"[{self.session_id}] Halting speech stream due to user interruption.")
                break

            async for audio_chunk in tts_engine.synthesize_stream(text=segment, voice=voice):
                if self._is_interrupted:
                    break
                if audio_chunk:
                    yield audio_chunk

        if not self._is_interrupted:
            self.set_state(VoiceState.IDLE)


class VoiceSessionRegistry:
    def __init__(self):
        self._sessions: Dict[str, VoiceSession] = {}

    def get_or_create(self, session_id: str, user_id: str) -> VoiceSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = VoiceSession(session_id=session_id, user_id=user_id)
        return self._sessions[session_id]

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


voice_session_registry = VoiceSessionRegistry()
