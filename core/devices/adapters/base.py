"""
SHIV AI — Base Device Adapter Contract
All operating system and environment adapters implement this uniform interface.
"""

from __future__ import annotations

import abc
import logging
import time
from typing import Any, Dict, Optional

from core.devices.emergency_stop import get_emergency_stop
from core.devices.observation import ScreenObservationService
from core.devices.types import (
    ActionRequest,
    DeviceCapabilities,
    DeviceType,
    ScreenObservation,
)

logger = logging.getLogger("shivai.devices.adapters")


class BaseDeviceAdapter(abc.ABC):
    """Abstract base class for all device adapters."""

    def __init__(self, device_id: str, device_type: DeviceType) -> None:
        self.device_id = device_id
        self.device_type = device_type
        self.is_connected = False
        self._emergency_stopped = False

        # Register with emergency stop
        get_emergency_stop().register_callback(self.emergency_stop)

    @abc.abstractmethod
    def connect(self) -> bool:
        """Connects or initializes communication with the device."""
        pass

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Closes connection to the device."""
        pass

    @abc.abstractmethod
    def ping(self) -> bool:
        """Pings device to verify connectivity."""
        pass

    def observe(self, include_screenshot: bool = False) -> ScreenObservation:
        """Captures active window and screen state."""
        return ScreenObservationService.observe(self.device_id, include_screenshot=include_screenshot)

    def execute(self, action: ActionRequest) -> Dict[str, Any]:
        """Validates emergency stop state and dispatches action."""
        get_emergency_stop().assert_not_stopped()
        if self._emergency_stopped:
            raise RuntimeError(f"Device '{self.device_id}' is locked in emergency stop state.")

        start_time = time.time()
        logger.info(f"Adapter [{self.device_id} ({self.device_type.value})] executing: {action.action_type.value}")
        output = self._dispatch_action(action)
        output["elapsed_ms"] = round((time.time() - start_time) * 1000, 2)
        return output

    @abc.abstractmethod
    def _dispatch_action(self, action: ActionRequest) -> Dict[str, Any]:
        """Subclass implementation of action dispatch."""
        pass

    def emergency_stop(self) -> None:
        """Immediately halts any in-progress device actions."""
        self._emergency_stopped = True
        logger.warning(f"Device adapter '{self.device_id}' entered emergency stop.")

    def reset_emergency_stop(self) -> None:
        self._emergency_stopped = False
