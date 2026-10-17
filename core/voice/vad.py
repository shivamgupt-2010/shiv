"""
ShivAI Voice Activity Detection (VAD) and Endpointing.
Analyzes audio frames to detect speech onset, silence intervals, and end-of-turn.
Designed with pure-Python audio signal processing to run with zero dependencies and low CPU on Render Free.
"""
import math
import struct
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("shivai.voice.vad")


class VoiceActivityDetector:
    """Detects presence of voice activity and turn endpointing."""

    def __init__(
        self,
        energy_threshold: float = 0.02,
        silence_timeout_ms: int = 1200,
        sample_rate: int = 16000,
    ):
        self.energy_threshold = energy_threshold
        self.silence_timeout_ms = silence_timeout_ms
        self.sample_rate = sample_rate
        self.is_speaking = False
        self.silence_duration_ms = 0
        self.speech_duration_ms = 0

    @staticmethod
    def calculate_rms(pcm_data: bytes) -> float:
        """Calculates Root Mean Square (RMS) energy of 16-bit PCM mono audio."""
        if not pcm_data or len(pcm_data) < 2:
            return 0.0

        num_samples = len(pcm_data) // 2
        try:
            samples = struct.unpack(f"<{num_samples}h", pcm_data[: num_samples * 2])
            sum_squares = sum(s * s for s in samples)
            rms = math.sqrt(sum_squares / num_samples) / 32768.0  # Normalize to 0.0 - 1.0
            return rms
        except Exception:
            return 0.0

    def process_frame(self, pcm_chunk: bytes, frame_duration_ms: int = 20) -> Dict[str, Any]:
        """
        Processes a single audio frame (e.g. 20ms of 16kHz audio = 640 bytes).
        Returns state transitions: speech_started, speech_ended, is_speaking.
        """
        rms = self.calculate_rms(pcm_chunk)
        has_voice = rms > self.energy_threshold

        speech_started = False
        speech_ended = False

        if has_voice:
            self.silence_duration_ms = 0
            self.speech_duration_ms += frame_duration_ms
            if not self.is_speaking and self.speech_duration_ms >= 100:  # 100ms debounce
                self.is_speaking = True
                speech_started = True
        else:
            if self.is_speaking:
                self.silence_duration_ms += frame_duration_ms
                if self.silence_duration_ms >= self.silence_timeout_ms:
                    self.is_speaking = False
                    speech_ended = True
                    self.speech_duration_ms = 0
                    self.silence_duration_ms = 0
            else:
                self.speech_duration_ms = 0

        return {
            "is_speaking": self.is_speaking,
            "speech_started": speech_started,
            "speech_ended": speech_ended,
            "rms_energy": round(rms, 4),
        }

    def reset(self) -> None:
        self.is_speaking = False
        self.silence_duration_ms = 0
        self.speech_duration_ms = 0
