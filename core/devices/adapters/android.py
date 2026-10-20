"""
SHIV AI — Android Device Automation Adapter
Controls connected Android devices (physical and emulated) via ADB shell,
Intent dispatch, Accessibility hierarchy inspection, and screen capture.
Does not require root access and respects Android sandbox permissions.
"""

from __future__ import annotations

import base64
import logging
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from core.devices.adapters.base import BaseDeviceAdapter
from core.devices.types import ActionRequest, ActionType, DeviceType

logger = logging.getLogger("shivai.devices.adapters.android")


class AndroidDeviceAdapter(BaseDeviceAdapter):
    """Adapter for Android mobile device automation via ADB and Intent wrappers."""

    def __init__(self, device_id: str = "android-device-primary", serial: Optional[str] = None) -> None:
        super().__init__(device_id=device_id, device_type=DeviceType.ANDROID)
        self.serial = serial
        self.adb_path = shutil.which("adb") or "adb"

    def _run_adb(self, args: List[str]) -> subprocess.CompletedProcess:
        """Executes an ADB command targeting the selected serial."""
        cmd = [self.adb_path]
        if self.serial:
            cmd.extend(["-s", self.serial])
        cmd.extend(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10)

    def connect(self) -> bool:
        """Verifies ADB executable and checks for connected devices."""
        try:
            res = subprocess.run([self.adb_path, "devices"], capture_output=True, text=True, timeout=5)
            lines = [line.strip() for line in res.stdout.splitlines() if line.strip() and not line.startswith("*")]
            # Filter device list
            devices = [line.split()[0] for line in lines[1:] if "device" in line]
            if devices:
                self.serial = self.serial or devices[0]
                self.is_connected = True
                logger.info(f"Android adapter connected to serial '{self.serial}'")
            else:
                self.is_connected = False
                logger.info("No authorized Android devices detected on ADB")
        except Exception as e:
            logger.debug(f"ADB discovery error: {e}")
            self.is_connected = False

        return self.is_connected

    def disconnect(self) -> None:
        self.is_connected = False

    def ping(self) -> bool:
        if not self.is_connected:
            return False
        try:
            res = self._run_adb(["get-state"])
            return "device" in res.stdout
        except Exception:
            return False

    def _dispatch_action(self, action: ActionRequest) -> Dict[str, Any]:
        atype = action.action_type
        params = action.params

        if atype == ActionType.LAUNCH_APP:
            return self.launch_app(package=action.target_app or params.get("package", ""))
        elif atype == ActionType.CLICK_ELEMENT:
            return self.tap(x=params.get("x", 500), y=params.get("y", 1000))
        elif atype == ActionType.ENTER_TEXT:
            return self.type_text(text=params.get("text", ""))
        elif atype == ActionType.KEY_PRESS:
            return self.key_event(keycode=params.get("keycode", 3))  # 3 = HOME
        elif atype == ActionType.CAPTURE_SCREEN:
            return self.capture_screenshot()
        elif atype == ActionType.OBSERVE_STATE:
            return self.dump_ui_hierarchy()
        else:
            return {"status": "unsupported", "action": atype.value}

    def launch_app(self, package: str) -> Dict[str, Any]:
        """Launches an installed Android application by package name."""
        if not package:
            raise ValueError("Android package name is required")

        if not self.is_connected:
            return {
                "launched": True,
                "simulated": True,
                "package": package,
                "note": "No ADB hardware device connected; simulated launch response.",
            }

        res = self._run_adb(["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"])
        return {
            "launched": res.returncode == 0,
            "package": package,
            "output": res.stdout.strip(),
        }

    def tap(self, x: int, y: int) -> Dict[str, Any]:
        """Simulates screen touch at coordinates (x, y)."""
        if not self.is_connected:
            return {"tapped": True, "simulated": True, "x": x, "y": y}

        res = self._run_adb(["shell", "input", "tap", str(x), str(y)])
        return {"tapped": res.returncode == 0, "x": x, "y": y}

    def type_text(self, text: str) -> Dict[str, Any]:
        """Types text via ADB input text."""
        from core.devices.security import SensitiveDataScrubber
        clean_text, redacted = SensitiveDataScrubber.scrub_text(text)
        escaped = clean_text.replace(" ", "%s").replace("&", "\\&")

        if not self.is_connected:
            return {"typed": True, "simulated": True, "text": clean_text, "redacted": redacted}

        res = self._run_adb(["shell", "input", "text", escaped])
        return {"typed": res.returncode == 0, "char_count": len(text), "redacted": redacted}

    def key_event(self, keycode: int) -> Dict[str, Any]:
        """Sends key event code (3 = HOME, 4 = BACK, 24 = VOL_UP, 25 = VOL_DOWN)."""
        if not self.is_connected:
            return {"key_sent": True, "simulated": True, "keycode": keycode}

        res = self._run_adb(["shell", "input", "keyevent", str(keycode)])
        return {"key_sent": res.returncode == 0, "keycode": keycode}

    def capture_screenshot(self) -> Dict[str, Any]:
        """Captures device display via adb screencap."""
        if not self.is_connected:
            return {"screenshot_b64": None, "simulated": True}

        try:
            cmd = [self.adb_path]
            if self.serial:
                cmd.extend(["-s", self.serial])
            cmd.extend(["exec-out", "screencap", "-p"])
            res = subprocess.run(cmd, capture_output=True, timeout=10)
            if res.returncode == 0 and res.stdout:
                b64 = base64.b64encode(res.stdout).decode("utf-8")
                return {"screenshot_b64": b64, "size_bytes": len(res.stdout)}
        except Exception as e:
            logger.error(f"ADB screencap failed: {e}")

        return {"screenshot_b64": None, "error": "screencap failed"}

    def dump_ui_hierarchy(self) -> Dict[str, Any]:
        """Extracts accessibility view hierarchy via uiautomator dump."""
        if not self.is_connected:
            return {"ui_hierarchy": "<hierarchy simulated='true' />"}

        self._run_adb(["shell", "uiautomator", "dump", "/sdcard/shiv_dump.xml"])
        res = self._run_adb(["shell", "cat", "/sdcard/shiv_dump.xml"])
        return {"ui_hierarchy": res.stdout.strip()}
