"""
Provider error categories and normalized exception definitions.
"""
from enum import Enum
from typing import Optional, Any, Dict


class ErrorCategory(str, Enum):
    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    TIMEOUT = "TIMEOUT"
    SERVER_ERROR = "SERVER_ERROR"
    BAD_REQUEST = "BAD_REQUEST"
    CONTEXT_TOO_LARGE = "CONTEXT_TOO_LARGE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN = "UNKNOWN"


class ProviderError(Exception):
    """Normalized provider-independent error representation."""

    def __init__(
        self,
        category: ErrorCategory,
        message: str,
        provider: str,
        model: Optional[str] = None,
        status_code: Optional[int] = None,
        raw_error: Optional[Any] = None,
        retry_after: Optional[int] = None,
    ):
        super().__init__(message)
        self.category = category
        self.message = message
        self.provider = provider
        self.model = model
        self.status_code = status_code
        self.raw_error = raw_error
        self.retry_after = retry_after

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "message": self.message,
            "provider": self.provider,
            "model": self.model,
            "status_code": self.status_code,
            "retry_after": self.retry_after,
        }
