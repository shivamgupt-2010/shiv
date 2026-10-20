"""
SHIV AI — Device Control & Automation Package
"""

from core.devices.emergency_stop import EmergencyStopManager, get_emergency_stop
from core.devices.observation import ScreenObservationService
from core.devices.permissions import DevicePermissionManager, get_device_permission_manager
from core.devices.registry import DeviceRegistry, get_device_registry
from core.devices.security import SensitiveDataScrubber
from core.devices.types import (
    ActionRequest,
    ActionResult,
    ActionType,
    ApprovalRequest,
    ApprovalStatus,
    DeviceCapabilities,
    DeviceRecord,
    DeviceStatus,
    DeviceType,
    RiskCategory,
    ScreenObservation,
    UIElement,
    UIRect,
    VerificationLevel,
    VerificationResult,
)
from core.devices.verification import TaskVerificationEngine

__all__ = [
    "DeviceType",
    "DeviceStatus",
    "RiskCategory",
    "ApprovalStatus",
    "VerificationLevel",
    "ActionType",
    "UIRect",
    "UIElement",
    "ScreenObservation",
    "DeviceCapabilities",
    "DeviceRecord",
    "ActionRequest",
    "ApprovalRequest",
    "VerificationResult",
    "ActionResult",
    "EmergencyStopManager",
    "get_emergency_stop",
    "SensitiveDataScrubber",
    "DevicePermissionManager",
    "get_device_permission_manager",
    "DeviceRegistry",
    "get_device_registry",
    "ScreenObservationService",
    "TaskVerificationEngine",
]
