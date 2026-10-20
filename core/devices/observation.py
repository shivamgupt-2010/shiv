"""
SHIV AI — Screen Observation & Window Identification Service
Extracts foreground window context, process information, UI element hierarchies,
and screen captures while sanitizing sensitive credentials.
"""

from __future__ import annotations

import base64
import io
import logging
import platform
import time
from typing import Any, Dict, List, Optional

import psutil

# PIL/ImageGrab is only available on Windows and macOS (requires a display server).
# On Linux (e.g. Render, Docker without Xvfb) it raises OSError — guard gracefully.
try:
    from PIL import Image, ImageGrab
    _PIL_AVAILABLE = True
except Exception:  # noqa: BLE001
    Image = None  # type: ignore[assignment]
    ImageGrab = None  # type: ignore[assignment]
    _PIL_AVAILABLE = False

from core.devices.security import SensitiveDataScrubber
from core.devices.types import (
    ScreenObservation,
    UIElement,
    UIRect,
)

logger = logging.getLogger("shivai.devices.observation")


class ScreenObservationService:
    """Observes desktop screen and active window states safely."""

    @classmethod
    def get_active_window_info(cls) -> Dict[str, Any]:
        """Cross-platform discovery of currently focused window, PID, and title."""
        title = "Active Workspace"
        proc_name = "explorer.exe" if platform.system() == "Windows" else "system"
        pid = 0
        rect = {"x": 0, "y": 0, "width": 1920, "height": 1080}

        try:
            if platform.system() == "Windows":
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    # Use InternalGetWindowText (non-blocking kernel read, avoids cross-process WM_GETTEXT hang)
                    buff = ctypes.create_unicode_buffer(512)
                    user32.InternalGetWindowText(hwnd, buff, 512)
                    title = buff.value or "Active Desktop Window"

                    # PID and Process Name safely
                    try:
                        lpdw_process_id = ctypes.c_ulong()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_process_id))
                        pid = lpdw_process_id.value
                        if pid > 0:
                            proc_name = psutil.Process(pid).name()
                    except Exception:
                        proc_name = "explorer.exe"


                    # Window Rect
                    class RECT(ctypes.Structure):
                        _fields_ = [
                            ("left", ctypes.c_long),
                            ("top", ctypes.c_long),
                            ("right", ctypes.c_long),
                            ("bottom", ctypes.c_long),
                        ]
                    r = RECT()
                    if user32.GetWindowRect(hwnd, ctypes.byref(r)):
                        rect = {
                            "x": r.left,
                            "y": r.top,
                            "width": max(0, r.right - r.left),
                            "height": max(0, r.bottom - r.top),
                        }
        except Exception as e:
            logger.debug(f"Native active window lookup fallback: {e}")

        # Scrub sensitive data from window title (e.g. Password Manager windows)
        clean_title, redacted_count = SensitiveDataScrubber.scrub_text(title)

        return {
            "title": clean_title,
            "process_name": proc_name,
            "pid": pid,
            "rect": rect,
            "redacted_count": redacted_count,
        }


    @classmethod
    def capture_screenshot_b64(cls, max_dim: int = 1280) -> Optional[str]:
        """Captures a single screenshot, resizes it, and encodes as base64 JPEG.
        Returns None on headless Linux/Docker environments where no display server is available.
        """
        if not _PIL_AVAILABLE or ImageGrab is None:
            logger.debug("Screenshot unavailable: PIL/ImageGrab not available on this platform")
            return None
        try:
            img = ImageGrab.grab()
            if img:
                # Resize if larger than max_dim to save bandwidth and fit memory
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="JPEG", quality=75)
                return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as e:
            logger.debug(f"Screenshot capture fallback: {e}")
        return None


    @classmethod
    def observe(
        cls,
        device_id: str,
        include_screenshot: bool = False,
    ) -> ScreenObservation:
        """Captures a complete snapshot of the device's visible state."""
        win_info = cls.get_active_window_info()

        # Build mock or discovered UI element tree
        ui_elements: List[UIElement] = [
            UIElement(
                element_id="el-titlebar",
                role="title_bar",
                name="TitleBar",
                text=win_info["title"],
                rect=UIRect(x=win_info["rect"]["x"], y=win_info["rect"]["y"], width=win_info["rect"]["width"], height=32),
            ),
            UIElement(
                element_id="el-main-client",
                role="client_area",
                name="MainWorkspace",
                text=f"Process: {win_info['process_name']}",
                rect=UIRect(x=win_info["rect"]["x"], y=win_info["rect"]["y"] + 32, width=win_info["rect"]["width"], height=win_info["rect"]["height"] - 32),
            ),
        ]

        screenshot_b64 = cls.capture_screenshot_b64() if include_screenshot else None

        return ScreenObservation(
            device_id=device_id,
            timestamp=time.time(),
            active_window_title=win_info["title"],
            active_process_name=win_info["process_name"],
            active_pid=win_info["pid"],
            window_rect=UIRect(**win_info["rect"]),
            ui_elements=ui_elements,
            screenshot_b64=screenshot_b64,
            redacted_secrets_count=win_info["redacted_count"],
            metadata={
                "os": platform.system(),
                "node": platform.node(),
            },
        )
