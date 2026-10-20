"""
SHIV AI — Device Security & Sensitive Data Scrubber
Prevents leakage of passwords, payment credentials, authentication tokens,
API keys, and personal secrets from logs, screenshots, clipboard, and LLM prompts.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


# Regex patterns for sensitive credentials
PATTERNS = [
    # API Keys & Bearer Tokens
    (re.compile(r"Bearer\s+([A-Za-z0-9\-_\.=]{8,})", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"(api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]\s*['\"]?([A-Za-z0-9\-_\.]{8,})['\"]?", re.IGNORECASE), r"\1: [REDACTED_KEY]"),
    # Credit Card Numbers (13-19 digits, Luhn check candidate)
    (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[REDACTED_PAYMENT_CARD]"),
    # Passwords & Secrets
    (re.compile(r"(password|passwd|pwd|passphrase)\s*[:=]\s*['\"]?([^'\"\s\r\n]{3,})['\"]?", re.IGNORECASE), r"\1: [REDACTED_PASSWORD]"),
    # Private Cryptographic Keys
    (re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+ PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    # JWT tokens
    (re.compile(r"eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+"), "[REDACTED_JWT]"),
]


class SensitiveDataScrubber:
    """Performs real-time scrubbing on text and structured parameters."""

    @classmethod
    def scrub_text(cls, text: str) -> Tuple[str, int]:
        """Scrubs secrets from a string. Returns (scrubbed_text, redaction_count)."""
        if not text:
            return text, 0

        redacted_count = 0
        cleaned = text
        for pattern, replacement in PATTERNS:
            matches = pattern.findall(cleaned)
            if matches:
                redacted_count += len(matches)
                cleaned = pattern.sub(replacement, cleaned)

        return cleaned, redacted_count

    @classmethod
    def scrub_dict(cls, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """Deeply scrub sensitive values in a dictionary."""
        total_redacted = 0
        scrubbed: Dict[str, Any] = {}

        sensitive_key_hints = {"password", "secret", "token", "apikey", "api_key", "auth", "credential", "credit_card", "cvv"}

        for k, v in data.items():
            k_lower = str(k).lower()
            if any(hint in k_lower for hint in sensitive_key_hints):
                scrubbed[k] = "[REDACTED_SECRET]"
                total_redacted += 1
            elif isinstance(v, str):
                v_clean, count = cls.scrub_text(v)
                scrubbed[k] = v_clean
                total_redacted += count
            elif isinstance(v, dict):
                v_clean_dict, count = cls.scrub_dict(v)
                scrubbed[k] = v_clean_dict
                total_redacted += count
            elif isinstance(v, list):
                scrubbed_list = []
                for item in v:
                    if isinstance(item, str):
                        item_clean, count = cls.scrub_text(item)
                        scrubbed_list.append(item_clean)
                        total_redacted += count
                    elif isinstance(item, dict):
                        item_clean_dict, count = cls.scrub_dict(item)
                        scrubbed_list.append(item_clean_dict)
                        total_redacted += count
                    else:
                        scrubbed_list.append(item)
                scrubbed[k] = scrubbed_list
            else:
                scrubbed[k] = v

        return scrubbed, total_redacted
