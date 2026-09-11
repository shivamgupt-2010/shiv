"""
ShivAI Official Python SDK.
"""
from sdk.shivai.client import ShivAI, AsyncShivAI
from sdk.shivai.types import (
    ChatResponse,
    StreamChunk,
    MemoryItem,
    ConversationItem,
    MessageItem,
)
from sdk.shivai.exceptions import (
    ShivAIError,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
    ServiceUnavailableError,
)

__version__ = "1.0.0"

__all__ = [
    "ShivAI",
    "AsyncShivAI",
    "ChatResponse",
    "StreamChunk",
    "MemoryItem",
    "ConversationItem",
    "MessageItem",
    "ShivAIError",
    "AuthenticationError",
    "RateLimitError",
    "NotFoundError",
    "ServiceUnavailableError",
]
