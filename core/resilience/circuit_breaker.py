"""
ShivAI Circuit Breaker.
Protects the system from cascading failures by temporarily stopping requests
to degraded external providers, then testing recovery before restoring normal traffic.
"""
import time
import asyncio
import logging
from enum import Enum
from typing import Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger("shivai.resilience.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"       # Normal operation: all requests allowed
    OPEN = "OPEN"           # Tripped: requests blocked to allow upstream recovery
    HALF_OPEN = "HALF_OPEN" # Probing: limited test requests allowed to verify recovery


class CircuitBreakerOpenException(Exception):
    """Raised when an execution is attempted on an open circuit breaker."""
    def __init__(self, key: str, time_remaining: float):
        super().__init__(f"Circuit breaker for '{key}' is OPEN. Retry in {time_remaining:.1f}s.")
        self.key = key
        self.time_remaining = time_remaining


class CircuitBreaker:
    """Manages failure tracking and state transitions for a single provider or key."""

    def __init__(
        self,
        name: str,
        failure_threshold: Optional[int] = None,
        recovery_timeout: Optional[float] = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold or settings.CIRCUIT_BREAKER_THRESHOLD
        self.recovery_timeout = recovery_timeout or settings.CIRCUIT_BREAKER_RECOVERY_SECONDS

        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_failure_time: float = 0.0
        self.last_state_change: float = time.time()
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        """Determines whether a request is allowed to proceed."""
        async with self._lock:
            now = time.time()
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                elapsed = now - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    logger.info(f"Circuit '{self.name}' transition: OPEN -> HALF_OPEN (probing recovery).")
                    self.state = CircuitState.HALF_OPEN
                    self.last_state_change = now
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                # Allow probe request
                return True

            return False

    async def record_success(self) -> None:
        """Records a successful upstream call, resetting or closing the circuit."""
        async with self._lock:
            self.success_count += 1
            if self.state == CircuitState.HALF_OPEN:
                logger.info(f"Circuit '{self.name}' probe succeeded. Transition: HALF_OPEN -> CLOSED.")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.last_state_change = time.time()
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    async def record_failure(self, error_message: str = "") -> None:
        """Records an upstream error and trips the breaker if threshold is exceeded."""
        async with self._lock:
            now = time.time()
            self.failure_count += 1
            self.last_failure_time = now

            if self.state == CircuitState.HALF_OPEN:
                logger.warning(
                    f"Circuit '{self.name}' probe failed ({error_message}). Transition: HALF_OPEN -> OPEN."
                )
                self.state = CircuitState.OPEN
                self.last_state_change = now
            elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit '{self.name}' exceeded {self.failure_threshold} failures ({error_message}). "
                    f"Transition: CLOSED -> OPEN for {self.recovery_timeout}s."
                )
                self.state = CircuitState.OPEN
                self.last_state_change = now

    def get_time_until_recovery(self) -> float:
        """Calculates seconds remaining before an OPEN circuit enters HALF_OPEN probe state."""
        if self.state != CircuitState.OPEN:
            return 0.0
        elapsed = time.time() - self.last_failure_time
        remaining = self.recovery_timeout - elapsed
        return max(0.0, remaining)

    def get_status(self) -> Dict[str, Any]:
        """Telemetry representation for health endpoints."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_sec": self.recovery_timeout,
            "seconds_until_retry": round(self.get_time_until_recovery(), 2),
        }


class CircuitBreakerRegistry:
    """Singleton registry tracking circuit breakers across all providers and model endpoints."""

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, name: str) -> CircuitBreaker:
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name)
            return self._breakers[name]

    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        return {name: cb.get_status() for name, cb in self._breakers.items()}


# Global Circuit Breaker Registry
circuit_breaker_registry = CircuitBreakerRegistry()
