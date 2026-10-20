"""
SHIV AI — Task Verification Engine
Provides empirical verification of action outcomes across files, windows,
network requests, and UI state changes, distinguishing between attempted,
accepted, completed, and independently verified results.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

from core.devices.observation import ScreenObservationService
from core.devices.types import (
    ActionRequest,
    ActionType,
    VerificationLevel,
    VerificationResult,
)

logger = logging.getLogger("shivai.devices.verification")


class TaskVerificationEngine:
    """Verifies whether an action produced its intended physical effect."""

    @classmethod
    def verify_file_created(
        cls,
        action_id: str,
        file_path: str,
        min_bytes: int = 1,
    ) -> VerificationResult:
        """Verifies that an exported/saved file physically exists on disk and is non-empty."""
        if not os.path.exists(file_path):
            return VerificationResult(
                action_id=action_id,
                level=VerificationLevel.FAILED,
                verified=False,
                evidence=f"File '{file_path}' was not found on filesystem",
            )

        try:
            size = os.path.getsize(file_path)
            if size < min_bytes:
                return VerificationResult(
                    action_id=action_id,
                    level=VerificationLevel.COMPLETED,
                    verified=False,
                    evidence=f"File exists but is empty or undersized ({size} bytes < {min_bytes})",
                    details={"size_bytes": size},
                )

            return VerificationResult(
                action_id=action_id,
                level=VerificationLevel.INDEPENDENTLY_VERIFIED,
                verified=True,
                evidence=f"File verified: exists on disk with size {size:,} bytes",
                details={"file_path": file_path, "size_bytes": size},
            )
        except Exception as e:
            return VerificationResult(
                action_id=action_id,
                level=VerificationLevel.FAILED,
                verified=False,
                evidence=f"Error inspecting file '{file_path}': {e}",
            )

    @classmethod
    def verify_window_active(
        cls,
        action_id: str,
        expected_title_fragment: str,
    ) -> VerificationResult:
        """Verifies that the target application or document title became the foreground window."""
        win = ScreenObservationService.get_active_window_info()
        title = win.get("title", "")
        proc = win.get("process_name", "")

        matched = (
            expected_title_fragment.lower() in title.lower()
            or expected_title_fragment.lower() in proc.lower()
        )

        if matched:
            return VerificationResult(
                action_id=action_id,
                level=VerificationLevel.INDEPENDENTLY_VERIFIED,
                verified=True,
                evidence=f"Foreground window verified: '{title}' ({proc}) matches expected '{expected_title_fragment}'",
                details=win,
            )
        else:
            return VerificationResult(
                action_id=action_id,
                level=VerificationLevel.COMPLETED,
                verified=False,
                evidence=f"Action completed, but active window is '{title}' ({proc}), expected '{expected_title_fragment}'",
                details=win,
            )

    @classmethod
    def verify_http_response(
        cls,
        action_id: str,
        status_code: int,
        expected_codes: Optional[list[int]] = None,
    ) -> VerificationResult:
        """Verifies an HTTP endpoint submission or API call."""
        expected = expected_codes or [200, 201, 202, 204]
        if status_code in expected:
            return VerificationResult(
                action_id=action_id,
                level=VerificationLevel.INDEPENDENTLY_VERIFIED,
                verified=True,
                evidence=f"HTTP response verified: status code {status_code} in expected {expected}",
                details={"status_code": status_code},
            )
        return VerificationResult(
            action_id=action_id,
            level=VerificationLevel.FAILED,
            verified=False,
            evidence=f"HTTP response error: status code {status_code} not in {expected}",
            details={"status_code": status_code},
        )

    @classmethod
    def verify_action(
        cls,
        action: ActionRequest,
        adapter_output: Dict[str, Any],
    ) -> VerificationResult:
        """General verifier routing based on action type."""
        # Check if output contains explicit file target
        if "file_path" in adapter_output:
            return cls.verify_file_created(action.action_id, adapter_output["file_path"])

        # Check if output contains expected window title
        if action.action_type in (ActionType.LAUNCH_APP, ActionType.SWITCH_WINDOW) and action.target_app:
            return cls.verify_window_active(action.action_id, action.target_app)

        # Check HTTP status if present
        if "status_code" in adapter_output:
            return cls.verify_http_response(action.action_id, adapter_output["status_code"])

        # Default completion verification
        return VerificationResult(
            action_id=action.action_id,
            level=VerificationLevel.COMPLETED,
            verified=True,
            evidence=f"Action {action.action_type.value} completed successfully with output keys: {list(adapter_output.keys())}",
            details=adapter_output,
        )
