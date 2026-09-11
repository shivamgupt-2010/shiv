"""
Token counter utility for estimating and calculating prompt token counts.
"""
from typing import List, Dict, Any

try:
    import tiktoken
    _encoder = tiktoken.get_encoding("cl100k_base")
except Exception:
    _encoder = None


def estimate_tokens(text: str) -> int:
    """Estimates token count for a text string."""
    if not text:
        return 0
    if _encoder is not None:
        try:
            return len(_encoder.encode(text))
        except Exception:
            pass
    # Fallback heuristic: 1 token ~= 3.8 - 4 characters in English
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    """Estimates total tokens for an array of chat messages."""
    total = 0
    for m in messages:
        # 3 tokens per message metadata overhead
        total += 3
        content = m.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    total += estimate_tokens(part["text"])
    total += 3  # priming tokens
    return total
