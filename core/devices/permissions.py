"""
SHIV AI — Permission & Approval Engine
Enforces the mandatory 3-Tier Policy Engine across all device interactions:
- Category A: Low-risk operations (reading, local drafting, previews) -> Auto-approved
- Category B: Consequential actions (publishing, sending emails, submitting forms) -> Explicit Approval Required
- Category C: Highly sensitive operations (financial transactions, credential updates, bulk delete) -> Strong Re-auth Required
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

from core.devices.emergency_stop import get_emergency_stop
from core.devices.types import (
    ActionRequest,
    ActionType,
    ApprovalRequest,
    ApprovalStatus,
    DeviceRecord,
    DeviceStatus,
    RiskCategory,
)

logger = logging.getLogger("shivai.devices.permissions")


# Default categorization by ActionType
ACTION_RISK_MAP: Dict[ActionType, RiskCategory] = {
    ActionType.OBSERVE_STATE: RiskCategory.CATEGORY_A_LOW,
    ActionType.CAPTURE_SCREEN: RiskCategory.CATEGORY_A_LOW,
    ActionType.READ_CONTENT: RiskCategory.CATEGORY_A_LOW,
    ActionType.LAUNCH_APP: RiskCategory.CATEGORY_A_LOW,
    ActionType.SWITCH_WINDOW: RiskCategory.CATEGORY_A_LOW,
    ActionType.SCROLL: RiskCategory.CATEGORY_A_LOW,
    ActionType.ORGANIZE_FILES: RiskCategory.CATEGORY_A_LOW,
    ActionType.EXPORT_MEDIA: RiskCategory.CATEGORY_A_LOW,

    ActionType.CLICK_ELEMENT: RiskCategory.CATEGORY_B_CONSEQUENTIAL,
    ActionType.ENTER_TEXT: RiskCategory.CATEGORY_B_CONSEQUENTIAL,
    ActionType.KEY_PRESS: RiskCategory.CATEGORY_B_CONSEQUENTIAL,
    ActionType.NAVIGATE_URL: RiskCategory.CATEGORY_B_CONSEQUENTIAL,
    ActionType.FILL_FORM: RiskCategory.CATEGORY_B_CONSEQUENTIAL,
    ActionType.SUBMIT_FORM: RiskCategory.CATEGORY_B_CONSEQUENTIAL,
    ActionType.SEND_EMAIL: RiskCategory.CATEGORY_B_CONSEQUENTIAL,
    ActionType.SEND_MESSAGE: RiskCategory.CATEGORY_B_CONSEQUENTIAL,
    ActionType.PUBLISH_POST: RiskCategory.CATEGORY_B_CONSEQUENTIAL,
    ActionType.REPLY_COMMENT: RiskCategory.CATEGORY_B_CONSEQUENTIAL,
    ActionType.CLOSE_APP: RiskCategory.CATEGORY_B_CONSEQUENTIAL,
    ActionType.EXECUTE_SCRIPT: RiskCategory.CATEGORY_B_CONSEQUENTIAL,
}


class DevicePermissionManager:
    """Manages device action permissions, evaluation, and approval lifecycle."""

    def __init__(self) -> None:
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._approval_history: List[ApprovalRequest] = []
        self._lock = threading.Lock()

        # Connect to emergency stop
        get_emergency_stop().register_callback(self._on_emergency_stop)

    def _on_emergency_stop(self) -> None:
        """Reject all pending approvals upon emergency stop trigger."""
        with self._lock:
            for appr in self._pending_approvals.values():
                appr.status = ApprovalStatus.EMERGENCY_STOPPED
                appr.decision_notes = "System Emergency Stop Triggered"
                appr.decided_at = time.time()
                self._approval_history.append(appr)
            self._pending_approvals.clear()
        logger.warning("DevicePermissionManager: Cleared all pending approvals due to Emergency Stop")

    def determine_risk(self, action: ActionRequest) -> RiskCategory:
        """Determines or verifies the risk level for an action request."""
        # Detect Category C triggers: financial, credential change, irreversible delete
        params_str = str(action.params).lower()
        sensitive_keywords = ["pay", "checkout", "transfer", "bank", "credit_card", "delete_all", "drop_table", "rm -rf", "password_reset", "change_password"]
        if any(kw in params_str for kw in sensitive_keywords):
            return RiskCategory.CATEGORY_C_SENSITIVE

        return ACTION_RISK_MAP.get(action.action_type, RiskCategory.CATEGORY_B_CONSEQUENTIAL)

    def evaluate_action(
        self,
        device: DeviceRecord,
        action: ActionRequest,
        user_id: str = "default_user",
    ) -> Tuple[bool, Optional[ApprovalRequest], str]:
        """
        Evaluates whether an action can execute immediately or requires human approval.
        Returns: (can_execute_now, approval_ticket_if_any, rationale)
        """
        # 1. Emergency stop check
        get_emergency_stop().assert_not_stopped()

        # 2. Device state check
        if device.status in (DeviceStatus.REVOKED, DeviceStatus.EMERGENCY_STOPPED, DeviceStatus.OFFLINE):
            return False, None, f"Device '{device.device_id}' is not operational (status: {device.status})"

        # 3. Application boundary check
        if action.target_app and device.allowed_applications != ["*"]:
            if action.target_app not in device.allowed_applications:
                return False, None, f"Application '{action.target_app}' is not permitted on device '{device.device_id}'"

        # 4. Risk categorization
        effective_risk = self.determine_risk(action)
        action.risk_category = effective_risk

        # Category A: Low risk -> Auto-execute
        if effective_risk == RiskCategory.CATEGORY_A_LOW and not action.requires_approval:
            return True, None, "Category A: Low-risk internal action auto-approved."

        # Category C: Sensitive -> Must have valid reauth token or create high-priority approval
        if effective_risk == RiskCategory.CATEGORY_C_SENSITIVE:
            if action.reauth_token and action.reauth_token.startswith("reauth-valid-"):
                return True, None, "Category C: Sensitive action authorized via valid re-authentication token."
            approval = self._create_approval_request(
                device=device,
                action=action,
                user_id=user_id,
                risk=RiskCategory.CATEGORY_C_SENSITIVE,
                summary=f"CRITICAL SENSITIVE ACTION: {action.action_type.value} on {action.target_app or 'device'}",
                consequences="May perform financial transactions, modify security credentials, or irreversibly alter data.",
            )
            return False, approval, "Category C: Highly sensitive action requires explicit human re-authorization."

        # Category B: Consequential -> Requires approval ticket
        approval = self._create_approval_request(
            device=device,
            action=action,
            user_id=user_id,
            risk=RiskCategory.CATEGORY_B_CONSEQUENTIAL,
            summary=f"Consequential action: {action.action_type.value} on {action.target_app or 'system'}",
            consequences="Will cause external side effects (send message, publish content, or interact with active UI).",
        )
        return False, approval, "Category B: External or consequential action requires explicit user approval."

    def _create_approval_request(
        self,
        device: DeviceRecord,
        action: ActionRequest,
        user_id: str,
        risk: RiskCategory,
        summary: str,
        consequences: str,
    ) -> ApprovalRequest:
        approval = ApprovalRequest(
            action_id=action.action_id,
            device_id=device.device_id,
            user_id=user_id,
            action_type=action.action_type,
            risk_category=risk,
            target_app=action.target_app or device.name,
            summary=summary,
            consequences=consequences,
            affected_content=action.params,
        )
        with self._lock:
            self._pending_approvals[approval.approval_id] = approval
        return approval

    def decide_approval(
        self,
        approval_id: str,
        approved: bool,
        user_id: str = "default_user",
        decision_notes: Optional[str] = None,
    ) -> ApprovalRequest:
        """Approves or rejects a pending action approval ticket."""
        get_emergency_stop().assert_not_stopped()

        with self._lock:
            approval = self._pending_approvals.get(approval_id)
            if not approval:
                raise KeyError(f"Approval ticket '{approval_id}' not found or already decided")

            if time.time() > approval.expires_at:
                approval.status = ApprovalStatus.EXPIRED
                approval.decision_notes = "Ticket expired before decision"
                del self._pending_approvals[approval_id]
                self._approval_history.append(approval)
                raise TimeoutError(f"Approval ticket '{approval_id}' has expired")

            approval.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            approval.decided_at = time.time()
            approval.decision_notes = decision_notes or (f"Decided by user {user_id}")
            del self._pending_approvals[approval_id]
            self._approval_history.append(approval)

        logger.info(f"Approval ticket '{approval_id}' {approval.status.value} by {user_id}")
        return approval

    def get_pending_approvals(self, user_id: Optional[str] = None) -> List[ApprovalRequest]:
        """Lists active pending approval tickets."""
        with self._lock:
            now = time.time()
            active = []
            for appr in list(self._pending_approvals.values()):
                if now > appr.expires_at:
                    appr.status = ApprovalStatus.EXPIRED
                    del self._pending_approvals[appr.approval_id]
                    self._approval_history.append(appr)
                    continue
                if user_id is None or appr.user_id == user_id:
                    active.append(appr)
            return sorted(active, key=lambda a: a.created_at, reverse=True)

    def get_approval(self, approval_id: str) -> Optional[ApprovalRequest]:
        with self._lock:
            if approval_id in self._pending_approvals:
                return self._pending_approvals[approval_id]
            for hist in self._approval_history:
                if hist.approval_id == approval_id:
                    return hist
            return None


_permission_manager_singleton = DevicePermissionManager()


def get_device_permission_manager() -> DevicePermissionManager:
    return _permission_manager_singleton
