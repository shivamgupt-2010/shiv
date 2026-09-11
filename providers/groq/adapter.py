"""
Groq Cloud Provider Adapter with Multi-Key Pooling and Instant Rate-Limit Failover.
"""
import time
from typing import Optional, List, Dict, Any, AsyncIterator
from config.settings import settings
from providers.base import UnifiedResponse, UnifiedStreamChunk
from providers.errors import ProviderError, ErrorCategory
from providers.openai.base_openai_compatible import BaseOpenAICompatibleProvider


class GroqProvider(BaseOpenAICompatibleProvider):
    """
    Groq Provider Adapter supporting multi-key pooling.
    If Key 1 is rate-limited (HTTP 429), it automatically rotates to Key 2.
    """

    def __init__(self, api_key: Optional[str] = None):
        configured_keys = settings.get_groq_keys()
        if api_key:
            self.api_keys = [api_key]
        elif configured_keys:
            self.api_keys = configured_keys
        else:
            self.api_keys = []

        primary_key = self.api_keys[0] if self.api_keys else None
        super().__init__(
            provider_name="groq",
            api_key=primary_key,
            base_url="https://api.groq.com/openai/v1",
        )
        self._current_key_idx = 0
        self._key_cooldowns: Dict[str, float] = {}

    def _get_active_key(self) -> Optional[str]:
        if not self.api_keys:
            return None

        now = time.time()
        # Find first key not currently under cooldown
        for _ in range(len(self.api_keys)):
            candidate = self.api_keys[self._current_key_idx]
            cooldown = self._key_cooldowns.get(candidate, 0.0)
            if now >= cooldown:
                return candidate
            # Rotate to next
            self._current_key_idx = (self._current_key_idx + 1) % len(self.api_keys)

        # If all keys in cooldown, return the one with earliest cooldown expiry
        earliest_key = min(self.api_keys, key=lambda k: self._key_cooldowns.get(k, 0.0))
        return earliest_key

    def _rotate_key(self, failed_key: str, cooldown_seconds: float = 30.0) -> None:
        self._key_cooldowns[failed_key] = time.time() + cooldown_seconds
        if len(self.api_keys) > 1:
            self._current_key_idx = (self._current_key_idx + 1) % len(self.api_keys)
            new_key = self.api_keys[self._current_key_idx]
            self.api_key = new_key

    async def generate(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> UnifiedResponse:
        """Executes generation with automatic multi-key retry."""
        keys_to_try = list(self.api_keys) if self.api_keys else [self.api_key]
        last_exception = None

        for attempt, key in enumerate(keys_to_try):
            self.api_key = self._get_active_key() or key
            try:
                return await super().generate(
                    model=model,
                    messages=messages,
                    options=options,
                    request_id=request_id,
                )
            except ProviderError as pe:
                last_exception = pe
                if pe.category in (ErrorCategory.RATE_LIMIT, ErrorCategory.QUOTA_EXHAUSTED, ErrorCategory.AUTH_ERROR):
                    cooldown = pe.retry_after or 45.0
                    self._rotate_key(self.api_key, cooldown_seconds=cooldown)
                    if attempt < len(keys_to_try) - 1:
                        continue
                raise pe
            except Exception as e:
                last_exception = e
                raise e

        if last_exception:
            raise last_exception
        raise ProviderError(category=ErrorCategory.UNKNOWN, message="Groq provider failed across all keys.", provider="groq")

    async def stream(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> AsyncIterator[UnifiedStreamChunk]:
        """Streams response using the active key from the pool."""
        self.api_key = self._get_active_key() or self.api_key
        try:
            async for chunk in super().stream(
                model=model,
                messages=messages,
                options=options,
                request_id=request_id,
            ):
                yield chunk
        except ProviderError as pe:
            if pe.category in (ErrorCategory.RATE_LIMIT, ErrorCategory.QUOTA_EXHAUSTED):
                self._rotate_key(self.api_key, cooldown_seconds=30.0)
            raise pe
