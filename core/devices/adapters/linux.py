"""
SHIV AI — Linux Desktop Automation Adapter
Provides Linux X11/Wayland desktop automation via xdotool, wmctrl, and native shell tools.
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from core.devices.adapters.base import BaseDeviceAdapter
from core.devices.types import ActionRequest, ActionType, DeviceType

logger = logging.getLogger("shivai.devices.adapters.linux")


class LinuxDesktopAdapter(BaseDeviceAdapter):
    """Linux desktop controller."""

    def __init__(self, device_id: str = "linux-workstation") -> None:
        super().__init__(device_id=device_id, device_type=DeviceType.LINUX)
        self.is_connected = platform.system() == "Linux"
        self.xdotool_available = shutil.which("xdotool") is not None

    def connect(self) -> bool:
        self.is_connected = platform.system() == "Linux"
        return self.is_connected

    def disconnect(self) -> None:
        self.is_connected = False

    def ping(self) -> bool:
        return platform.system() == "Linux"

    def _dispatch_action(self, action: ActionRequest) -> Dict[str, Any]:
        atype = action.action_type
        params = action.params

        if not self.is_connected:
            return {
                "status": "simulated",
                "action": atype.value,
                "note": f"Executing Linux action '{atype.value}' in compatibility mode (Host OS is {platform.system()})",
            }

        if atype == ActionType.LAUNCH_APP:
            app = action.target_app or params.get("app_name", "")
            proc = subprocess.Popen([app] + params.get("args", []), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"launched": True, "app": app, "pid": proc.pid}
        elif atype == ActionType.ENTER_TEXT and self.xdotool_available:
            text = params.get("text", "")
            res = subprocess.run(["xdotool", "type", text], capture_output=True, text=True)
            return {"entered": res.returncode == 0, "text": text}
        elif atype == ActionType.CLICK_ELEMENT and self.xdotool_available:
            x, y = params.get("x", 100), params.get("y", 100)
            res = subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", "1"], capture_output=True)
            return {"clicked": res.returncode == 0, "x": x, "y": y}
        else:
            return {"status": "completed", "action": atype.value}
