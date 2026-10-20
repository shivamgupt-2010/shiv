"""
SHIV AI — Emergency Stop Mechanism
Provides an instantaneous, thread-safe system-wide kill switch to immediately
halt all active device interactions, reject pending approvals, and prevent
any unauthorized external or local side effects.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("shivai.devices.emergency_stop")


class EmergencyStopActiveError(RuntimeError):
    """Raised whenever an action is attempted while the emergency stop is active."""
    pass


class EmergencyStopManager:
    """
    Central emergency stop manager.
    Can be triggered via API, UI button, or programmatically upon anomaly detection.
    """

    _instance: Optional[EmergencyStopManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> EmergencyStopManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._is_active = False
                cls._instance._reason = ""
                cls._instance._triggered_by = ""
                cls._instance._triggered_at = 0.0
                cls._instance._callbacks: List[Callable[[], None]] = []
                cls._instance._state_lock = threading.Lock()
            return cls._instance

    @property
    def is_active(self) -> bool:
        with self._state_lock:
            return self._is_active

    @property
    def details(self) -> Dict[str, Any]:
        with self._state_lock:
            return {
                "is_active": self._is_active,
                "reason": self._reason,
                "triggered_by": self._triggered_by,
                "triggered_at": self._triggered_at,
            }

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register a cleanup/halt callback triggered when emergency stop fires."""
        with self._state_lock:
            self._callbacks.append(callback)

    def trigger(self, user_id: str = "user", reason: str = "User initiated emergency stop") -> Dict[str, Any]:
        """Trigger immediate emergency stop."""
        with self._state_lock:
            self._is_active = True
            self._reason = reason
            self._triggered_by = user_id
            self._triggered_at = time.time()
            callbacks_to_run = list(self._callbacks)

        logger.critical(f"EMERGENCY STOP TRIGGERED by {user_id}: {reason}")

        # Execute registered adapter kill callbacks
        for cb in callbacks_to_run:
            try:
                cb()
            except Exception as e:
                logger.error(f"Error in emergency stop callback: {e}")

        return self.details

    def reset(self, user_id: str = "user") -> Dict[str, Any]:
        """Reset the emergency stop state after inspection."""
        with self._state_lock:
            self._is_active = False
            self._reason = ""
            self._triggered_by = ""
            self._triggered_at = 0.0

        logger.warning(f"Emergency stop reset by {user_id}")
        return self.details

    def assert_not_stopped(self) -> None:
        """Raises EmergencyStopActiveError if the kill switch is currently active."""
        with self._state_lock:
            if self._is_active:
                raise EmergencyStopActiveError(
                    f"Action blocked: Emergency Stop is active! (Reason: '{self._reason}' triggered at {self._triggered_at})"
                )


_emergency_stop_singleton = EmergencyStopManager()


def get_emergency_stop() -> EmergencyStopManager:
    return _emergency_stop_singleton
