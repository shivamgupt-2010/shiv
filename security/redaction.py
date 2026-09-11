"""
Secret and Sensitive-Data Redaction Engine.
Ensures API keys, tokens, and credentials never leak into logs, traces, or client responses.
"""
import re
from typing import List, Optional
from config.settings import settings


class SecretRedactor:
    def __init__(self):
        # Known vendor key regex patterns
        self._patterns = [
            re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),          # OpenAI / generic
            re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),      # Anthropic
            re.compile(r"AIza[0-9A-Za-z-_]{20,}", re.IGNORECASE),          # Google Gemini
            re.compile(r"gsk_[a-zA-Z0-9_-]{20,}", re.IGNORECASE),         # Groq
            re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE), # Generic Bearer
        ]

    def redact(self, text: str) -> str:
        """Redacts all configured secrets and pattern-matched API keys from text."""
        if not text:
            return ""

        redacted = str(text)

        # 1. Exact string substitution for all known configured secrets
        known_secrets = settings.get_secret_keys_for_redaction()
        for secret in known_secrets:
            if secret in redacted:
                redacted = redacted.replace(secret, "[REDACTED_SECRET]")

        # 2. Pattern-based redaction
        for pattern in self._patterns:
            redacted = pattern.sub("[REDACTED_API_KEY]", redacted)

        return redacted


redactor = SecretRedactor()


def redact_secrets(text: str) -> str:
    return redactor.redact(text)
