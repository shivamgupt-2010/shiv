"""
SHIV AI — Windows Desktop Automation Adapter
Executes native Windows desktop operations through Win32 User32 APIs,
subprocess execution, window focus management, and keyboard/mouse simulation.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import time
from typing import Any, Dict, List, Optional

import psutil

from core.devices.adapters.base import BaseDeviceAdapter
from core.devices.types import ActionRequest, ActionType, DeviceType

logger = logging.getLogger("shivai.devices.adapters.windows")


class WindowsDesktopAdapter(BaseDeviceAdapter):
    """Native Windows desktop controller."""

    def __init__(self, device_id: str = "host-local-primary") -> None:
        super().__init__(device_id=device_id, device_type=DeviceType.WINDOWS)
        self.is_connected = platform.system() == "Windows"

    def connect(self) -> bool:
        self.is_connected = platform.system() == "Windows"
        return self.is_connected

    def disconnect(self) -> None:
        self.is_connected = False

    def ping(self) -> bool:
        return platform.system() == "Windows"

    def _dispatch_action(self, action: ActionRequest) -> Dict[str, Any]:
        """Dispatches action to specific Windows implementation method."""
        atype = action.action_type
        params = action.params

        if atype == ActionType.LAUNCH_APP:
            return self.launch_app(
                app_name=action.target_app or params.get("app_name", ""),
                args=params.get("args", []),
            )
        elif atype == ActionType.CLOSE_APP:
            return self.close_app(process_name=action.target_app or params.get("process_name", ""))
        elif atype == ActionType.SWITCH_WINDOW:
            return self.switch_window(title_fragment=params.get("title", action.target_app))
        elif atype == ActionType.CLICK_ELEMENT:
            return self.click(x=params.get("x", 100), y=params.get("y", 100))
        elif atype == ActionType.ENTER_TEXT:
            return self.enter_text(text=params.get("text", ""))
        elif atype == ActionType.KEY_PRESS:
            return self.key_press(key=params.get("key", "Enter"))
        elif atype == ActionType.SCROLL:
            return self.scroll(clicks=params.get("clicks", 1))
        elif atype == ActionType.CAPTURE_SCREEN:
            obs = self.observe(include_screenshot=True)
            return {"screenshot_b64": obs.screenshot_b64, "active_window": obs.active_window_title}
        elif atype == ActionType.OBSERVE_STATE:
            obs = self.observe(include_screenshot=False)
            return obs.model_dump()
        else:
            return {"status": "unsupported_or_simulated", "action": atype.value, "params": params}

    def launch_app(self, app_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Launches a desktop application executable."""
        if not app_name:
            raise ValueError("Application name is required to launch")

        cmd = [app_name] + (args or [])
        try:
            # Use shell=True on Windows to resolve common PATH shortcuts like 'calc', 'notepad'
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.3)
            return {
                "launched": True,
                "app_name": app_name,
                "pid": proc.pid,
                "status": "running",
            }
        except Exception as e:
            logger.error(f"Failed to launch app '{app_name}': {e}")
            return {"launched": False, "app_name": app_name, "error": str(e)}

    def close_app(self, process_name: str) -> Dict[str, Any]:
        """Terminates processes matching process_name."""
        if not process_name:
            raise ValueError("Process name is required")

        terminated_pids = []
        clean_name = process_name.lower().replace(".exe", "")
        for p in psutil.process_iter(["pid", "name"]):
            try:
                pname = (p.info["name"] or "").lower().replace(".exe", "")
                if pname == clean_name:
                    p.terminate()
                    terminated_pids.append(p.info["pid"])
            except Exception:
                continue

        return {
            "closed": len(terminated_pids) > 0,
            "process_name": process_name,
            "terminated_pids": terminated_pids,
        }

    def switch_window(self, title_fragment: str) -> Dict[str, Any]:
        """Brings a window with matching title fragment to the foreground."""
        if platform.system() != "Windows":
            return {"focused": False, "reason": "Not running on Windows"}

        import ctypes
        user32 = ctypes.windll.user32
        matched_hwnd = None

        def enum_windows_proc(hwnd, lParam):
            nonlocal matched_hwnd
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if title_fragment.lower() in buff.value.lower():
                        matched_hwnd = hwnd
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)

        if matched_hwnd:
            user32.ShowWindow(matched_hwnd, 9)  # SW_RESTORE = 9
            user32.SetForegroundWindow(matched_hwnd)
            return {"focused": True, "title_fragment": title_fragment, "hwnd": matched_hwnd}

        return {"focused": False, "title_fragment": title_fragment, "reason": "No matching window found"}

    def click(self, x: int, y: int) -> Dict[str, Any]:
        """Simulates mouse click at coordinates (x, y)."""
        if platform.system() == "Windows":
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetCursorPos(x, y)
            time.sleep(0.05)
            user32.mouse_event(2, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN = 0x0002
            time.sleep(0.05)
            user32.mouse_event(4, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP = 0x0004
            return {"clicked": True, "x": x, "y": y}
        return {"clicked": True, "simulated": True, "x": x, "y": y}

    def enter_text(self, text: str) -> Dict[str, Any]:
        """Types text into the currently active window."""
        # Clean text
        from core.devices.security import SensitiveDataScrubber
        clean_text, redacted = SensitiveDataScrubber.scrub_text(text)

        if platform.system() == "Windows":
            import ctypes
            user32 = ctypes.windll.user32
            # Simulate key presses using VkKeyScanW
            for char in text:
                vk = user32.VkKeyScanW(ord(char))
                vk_code = vk & 0xFF
                if vk_code:
                    user32.keybd_event(vk_code, 0, 0, 0)
                    time.sleep(0.01)
                    user32.keybd_event(vk_code, 0, 2, 0)  # KEYEVENTF_KEYUP = 2
            return {"entered": True, "char_count": len(text), "redacted_count": redacted}

        return {"entered": True, "simulated": True, "char_count": len(text)}

    def key_press(self, key: str) -> Dict[str, Any]:
        """Presses a special key (Enter, Tab, Escape, etc.)."""
        key_map = {
            "enter": 0x0D,
            "return": 0x0D,
            "tab": 0x09,
            "escape": 0x1B,
            "esc": 0x1B,
            "space": 0x20,
            "backspace": 0x08,
            "up": 0x26,
            "down": 0x28,
            "left": 0x25,
            "right": 0x27,
        }
        vk_code = key_map.get(key.lower(), 0x0D)
        if platform.system() == "Windows":
            import ctypes
            user32 = ctypes.windll.user32
            user32.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.02)
            user32.keybd_event(vk_code, 0, 2, 0)
            return {"key_pressed": key, "vk_code": hex(vk_code)}

        return {"key_pressed": key, "simulated": True}

    def scroll(self, clicks: int = 1) -> Dict[str, Any]:
        """Scrolls mouse wheel by clicks count."""
        if platform.system() == "Windows":
            import ctypes
            user32 = ctypes.windll.user32
            user32.mouse_event(0x0800, 0, 0, clicks * 120, 0)  # MOUSEEVENTF_WHEEL = 0x0800
            return {"scrolled": True, "clicks": clicks}
        return {"scrolled": True, "simulated": True, "clicks": clicks}
