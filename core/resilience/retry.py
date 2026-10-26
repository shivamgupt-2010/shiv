"""
ShivAI Asynchronous Retry Engine.
Executes async tasks with exponential backoff and jitter, strictly retrying
transient faults (429, 500, 502, 503, 504, Timeout) and never retrying client/auth errors.
"""
import asyncio
import random
import logging
from typing import Callable, TypeVar, Awaitable, Optional, Any
from config.settings import settings
from providers.errors import ProviderError, ErrorCategory

logger = logging.getLogger("shivai.resilience.retry")

T = TypeVar("T")


def is_error_retryable(exc: Exception) -> bool:
    """Classifies whether an exception represents a transient, retryable failure."""
    if isinstance(exc, ProviderError):
        return exc.is_retryable

    # Check for asyncio timeout
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True

    # Check for HTTP status codes if present on exception object
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status_code, int) and status_code in {429, 500, 502, 503, 504}:
        return True

    # Check for typical transient network errors
    err_str = str(exc).lower()
    retryable_keywords = [
        "rate limit", "ratelimit", "too many requests", "429",
        "connection reset", "broken pipe", "server disconnected",
        "timeout", "timed out", "service unavailable", "503", "502", "bad gateway"
    ]
    if any(k in err_str for k in retryable_keywords):
        return True

    return False


async def execute_with_retry(
    operation: Callable[[], Awaitable[T]],
    max_retries: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    operation_name: str = "upstream_call",
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> T:
    """
    Executes an async callable with bounded exponential backoff and full jitter.
    
    Formula: delay = min(max_delay, base_delay * (2 ** attempt)) * random(0.8, 1.2)
    """
    retries = max_retries if max_retries is not None else settings.ROUTER_MAX_RETRIES
    b_delay = base_delay if base_delay is not None else settings.RETRY_BASE_DELAY_SECONDS
    m_delay = max_delay if max_delay is not None else settings.RETRY_MAX_DELAY_SECONDS

    last_exc: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            return await operation()
        except Exception as exc:
            last_exc = exc
            
            # If maximum attempts reached or error is not retryable, re-raise immediately
            if attempt == retries or not is_error_retryable(exc):
                if not is_error_retryable(exc):
                    logger.info(f"[{operation_name}] Non-retryable error encountered ({type(exc).__name__}): {exc}")
                raise exc

            # Calculate backoff with jitter
            raw_backoff = min(m_delay, b_delay * (2 ** attempt))
            jitter = random.uniform(0.75, 1.25)
            delay = round(raw_backoff * jitter, 3)

            # Check if ProviderError specifies a custom retry-after header
            if isinstance(exc, ProviderError) and exc.retry_after and exc.retry_after > 0:
                delay = min(m_delay, float(exc.retry_after))

            logger.warning(
                f"[{operation_name}] Transient failure on attempt {attempt + 1}/{retries + 1} "
                f"({exc}). Backing off for {delay:.2f}s..."
            )

            if on_retry:
                try:
                    on_retry(attempt + 1, exc, delay)
                except Exception:
                    pass

            await asyncio.sleep(delay)

    raise last_exc or RuntimeError("Retry loop exited unexpectedly without result or exception.")
