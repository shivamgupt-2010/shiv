"""
ShivAI Key Pool Manager.
Tracks key health, rate-limit cooldowns, auth failures, and auto-rotates
without ever exposing raw secrets in logs, responses, or exceptions.
"""
import time
import hashlib
import asyncio
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("shivai.resilience.key_pool")


class KeyState(BaseModel):
    provider: str
    key_id: str                      # Safe fingerprint (e.g., "groq_key_...a1b2")
    enabled: bool = True
    healthy: bool = True
    failure_count: int = 0
    rate_limited_until: float = 0.0
    last_used: float = 0.0
    last_success: float = 0.0
    last_failure: float = 0.0
    last_error_reason: str = ""

    @property
    def is_available(self) -> bool:
        if not self.enabled or not self.healthy:
            return False
        if self.rate_limited_until > time.time():
            return False
        return True


def mask_secret(secret: str) -> str:
    """Produces a secure non-reversible fingerprint like 'key_f83a...91c2'."""
    if not secret:
        return "empty"
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    return f"key_{digest[:6]}...{digest[-4:]}"


class ProviderKeyPool:
    """Pool of keys for a specific provider supporting round-robin, failover, and cooldowns."""

    def __init__(self, provider: str, keys: List[str]):
        self.provider = provider
        self._raw_keys: List[str] = [k.strip() for k in keys if k and k.strip()]
        self._key_states: Dict[str, KeyState] = {}
        self._index: int = 0
        self._lock = asyncio.Lock()

        for raw_k in self._raw_keys:
            kid = f"{provider}_{mask_secret(raw_k)}"
            self._key_states[raw_k] = KeyState(provider=provider, key_id=kid)

    async def get_next_available_key(self) -> Optional[str]:
        """Returns the next available, healthy, and non-cooldown API key."""
        async with self._lock:
            if not self._raw_keys:
                return None

            now = time.time()
            total = len(self._raw_keys)

            for i in range(total):
                idx = (self._index + i) % total
                candidate_key = self._raw_keys[idx]
                state = self._key_states[candidate_key]

                if state.is_available:
                    self._index = (idx + 1) % total
                    state.last_used = now
                    return candidate_key

            return None

    async def record_success(self, raw_key: str) -> None:
        """Records a successful API call with this key."""
        async with self._lock:
            state = self._key_states.get(raw_key)
            if state:
                state.last_success = time.time()
                state.failure_count = 0
                state.healthy = True
                state.rate_limited_until = 0.0

    async def record_rate_limit(self, raw_key: str, cooldown_seconds: float = 60.0) -> None:
        """Temporarily puts the key in cooldown due to a 429 response."""
        async with self._lock:
            state = self._key_states.get(raw_key)
            if state:
                now = time.time()
                state.rate_limited_until = now + cooldown_seconds
                state.last_failure = now
                state.failure_count += 1
                state.last_error_reason = "RATE_LIMIT"
                logger.warning(
                    f"Key {state.key_id} for provider '{self.provider}' rate-limited. "
                    f"Cooldown set for {cooldown_seconds}s."
                )

    async def record_auth_failure(self, raw_key: str, reason: str = "Invalid API Key") -> None:
        """Permanently disables the key for this run upon authentication failure."""
        async with self._lock:
            state = self._key_states.get(raw_key)
            if state:
                state.enabled = False
                state.healthy = False
                state.last_failure = time.time()
                state.last_error_reason = reason
                logger.error(
                    f"Key {state.key_id} for provider '{self.provider}' failed authentication: {reason}. "
                    f"Key disabled to prevent continuous retries."
                )

    def get_pool_status(self) -> List[Dict[str, Any]]:
        """Returns safe telemetry for monitoring without exposing raw keys."""
        return [state.model_dump() for state in self._key_states.values()]


class GlobalKeyPoolManager:
    """Coordinates key pools across all external providers."""

    def __init__(self):
        self._pools: Dict[str, ProviderKeyPool] = {}
        self._lock = asyncio.Lock()

    async def initialize_from_settings(self) -> None:
        """Populates key pools from configured settings."""
        async with self._lock:
            # Groq
            groq_keys = settings.get_groq_keys()
            if groq_keys:
                self._pools["groq"] = ProviderKeyPool("groq", groq_keys)

            # Gemini
            if settings.GEMINI_API_KEY:
                self._pools["gemini"] = ProviderKeyPool("gemini", [settings.GEMINI_API_KEY])

            # OpenAI
            if settings.OPENAI_API_KEY:
                self._pools["openai"] = ProviderKeyPool("openai", [settings.OPENAI_API_KEY])

            # Anthropic
            if settings.ANTHROPIC_API_KEY:
                self._pools["anthropic"] = ProviderKeyPool("anthropic", [settings.ANTHROPIC_API_KEY])

            # DeepSeek
            if settings.DEEPSEEK_API_KEY:
                self._pools["deepseek"] = ProviderKeyPool("deepseek", [settings.DEEPSEEK_API_KEY])

            # Mistral
            if settings.MISTRAL_API_KEY:
                self._pools["mistral"] = ProviderKeyPool("mistral", [settings.MISTRAL_API_KEY])

            # Generic OpenAI
            if settings.GENERIC_OPENAI_API_KEY:
                self._pools["generic_openai"] = ProviderKeyPool("generic_openai", [settings.GENERIC_OPENAI_API_KEY])

    async def get_key_for_provider(self, provider: str) -> Optional[str]:
        pool = self._pools.get(provider)
        if not pool:
            return None
        return await pool.get_next_available_key()

    async def record_key_success(self, provider: str, raw_key: str) -> None:
        pool = self._pools.get(provider)
        if pool:
            await pool.record_success(raw_key)

    async def record_key_rate_limit(self, provider: str, raw_key: str, cooldown_seconds: float = 60.0) -> None:
        pool = self._pools.get(provider)
        if pool:
            await pool.record_rate_limit(raw_key, cooldown_seconds)

    async def record_key_auth_failure(self, provider: str, raw_key: str, reason: str = "") -> None:
        pool = self._pools.get(provider)
        if pool:
            await pool.record_auth_failure(raw_key, reason)

    def get_all_statuses(self) -> Dict[str, List[Dict[str, Any]]]:
        return {provider: pool.get_pool_status() for provider, pool in self._pools.items()}


# Global Key Pool Manager
key_pool_manager = GlobalKeyPoolManager()
