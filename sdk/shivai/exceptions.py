"""
ShivAI SDK Exceptions.
"""
from typing import Optional, Dict, Any


class ShivAIError(Exception):
    """Base exception for all ShivAI SDK operations."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body or {}


class AuthenticationError(ShivAIError):
    """Raised when the API key is missing or invalid (HTTP 401)."""
    pass


class RateLimitError(ShivAIError):
    """Raised when client request rate limit is exceeded (HTTP 429)."""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class NotFoundError(ShivAIError):
    """Raised when a requested resource (conversation, memory) is not found (HTTP 404)."""
    pass


class ServiceUnavailableError(ShivAIError):
    """Raised when all underlying AI model providers are exhausted (HTTP 503)."""
    pass
