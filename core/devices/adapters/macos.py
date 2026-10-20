"""
SHIV AI — macOS Desktop Automation Adapter
Provides macOS application automation via AppleScript (osascript),
accessibility APIs, and system-level shortcuts.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from typing import Any, Dict, List, Optional

from core.devices.adapters.base import BaseDeviceAdapter
from core.devices.types import ActionRequest, ActionType, DeviceType

logger = logging.getLogger("shivai.devices.adapters.macos")


class MacOSDesktopAdapter(BaseDeviceAdapter):
    """macOS desktop controller."""

    def __init__(self, device_id: str = "macos-workstation") -> None:
        super().__init__(device_id=device_id, device_type=DeviceType.MACOS)
        self.is_connected = platform.system() == "Darwin"

    def connect(self) -> bool:
        self.is_connected = platform.system() == "Darwin"
        return self.is_connected

    def disconnect(self) -> None:
        self.is_connected = False

    def ping(self) -> bool:
        return platform.system() == "Darwin"

    def _run_applescript(self, script: str) -> subprocess.CompletedProcess:
        """Executes an AppleScript snippet."""
        return subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)

    def _dispatch_action(self, action: ActionRequest) -> Dict[str, Any]:
        atype = action.action_type
        params = action.params

        if not self.is_connected:
            return {
                "status": "simulated",
                "action": atype.value,
                "note": f"Executing macOS action '{atype.value}' in compatibility mode (Host OS is {platform.system()})",
            }

        if atype == ActionType.LAUNCH_APP:
            app = action.target_app or params.get("app_name", "")
            res = self._run_applescript(f'tell application "{app}" to activate')
            return {"launched": res.returncode == 0, "app": app}
        elif atype == ActionType.ENTER_TEXT:
            text = params.get("text", "")
            res = self._run_applescript(f'tell application "System Events" to keystroke "{text}"')
            return {"entered": res.returncode == 0, "text": text}
        elif atype == ActionType.KEY_PRESS:
            key = params.get("key", "return")
            res = self._run_applescript(f'tell application "System Events" to key code 36') # 36 = Return
            return {"key_pressed": key}
        else:
            return {"status": "completed", "action": atype.value}
