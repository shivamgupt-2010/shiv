"""
SHIV AI — Universal Device Operator: Core Types & Data Models
Defines enumeration standards, request/response models, permission tiers,
and verification levels across Windows, macOS, Linux, Android, and Browser.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    ANDROID = "android"
    BROWSER = "browser"
    REMOTE_DESKTOP = "remote_desktop"
    CREATIVE_APP = "creative_app"


class DeviceStatus(str, Enum):
    OFFLINE = "offline"
    CONNECTING = "connecting"
    ONLINE = "online"
    BUSY = "busy"
    PAUSED = "paused"
    REVOKED = "revoked"
    EMERGENCY_STOPPED = "emergency_stopped"


class RiskCategory(str, Enum):
    """
    Mandatory 3-tier risk classification:
    - CATEGORY_A_LOW: Reading authorized documents, editing local drafts, file organization. Auto-executable.
    - CATEGORY_B_CONSEQUENTIAL: Publishing social posts, sending messages/emails, submitting forms. Explicit approval required.
    - CATEGORY_C_SENSITIVE: Financial transactions, security settings changes, bulk destructive operations. Strong confirmation & re-auth.
    """
    CATEGORY_A_LOW = "category_a_low"
    CATEGORY_B_CONSEQUENTIAL = "category_b_consequential"
    CATEGORY_C_SENSITIVE = "category_c_sensitive"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EMERGENCY_STOPPED = "emergency_stopped"


class VerificationLevel(str, Enum):
    """
    Distinguishes state verification progression:
    Attempted -> Accepted by target -> Completed -> Independently Verified
    """
    ATTEMPTED = "attempted"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    INDEPENDENTLY_VERIFIED = "independently_verified"
    FAILED = "failed"


class ActionType(str, Enum):
    # Desktop / Mobile UI
    LAUNCH_APP = "launch_app"
    CLOSE_APP = "close_app"
    CLICK_ELEMENT = "click_element"
    ENTER_TEXT = "enter_text"
    KEY_PRESS = "key_press"
    SCROLL = "scroll"
    SWITCH_WINDOW = "switch_window"
    CAPTURE_SCREEN = "capture_screen"
    OBSERVE_STATE = "observe_state"
    # Web & Browser
    NAVIGATE_URL = "navigate_url"
    READ_CONTENT = "read_content"
    FILL_FORM = "fill_form"
    SUBMIT_FORM = "submit_form"
    # Communications & Social Media
    SEND_EMAIL = "send_email"
    SEND_MESSAGE = "send_message"
    PUBLISH_POST = "publish_post"
    REPLY_COMMENT = "reply_comment"
    # Creative & Filesystem
    EXECUTE_SCRIPT = "execute_script"
    EXPORT_MEDIA = "export_media"
    ORGANIZE_FILES = "organize_files"


class UIRect(BaseModel):
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


class UIElement(BaseModel):
    element_id: str
    role: str = "element"
    name: str = ""
    text: str = ""
    rect: UIRect = Field(default_factory=UIRect)
    enabled: bool = True
    focused: bool = False
    children: List[UIElement] = Field(default_factory=list)


class ScreenObservation(BaseModel):
    device_id: str
    timestamp: float = Field(default_factory=time.time)
    active_window_title: str = ""
    active_process_name: str = ""
    active_pid: int = 0
    window_rect: UIRect = Field(default_factory=UIRect)
    ui_elements: List[UIElement] = Field(default_factory=list)
    screenshot_b64: Optional[str] = None
    redacted_secrets_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DeviceCapabilities(BaseModel):
    supports_screen_capture: bool = True
    supports_input_simulation: bool = True
    supports_accessibility_tree: bool = True
    supports_browser_automation: bool = True
    supports_adb: bool = False
    supports_file_transfer: bool = True
    screen_resolution: str = "1920x1080"
    os_version: str = "unknown"
    extra_capabilities: List[str] = Field(default_factory=list)


class DeviceRecord(BaseModel):
    device_id: str
    name: str
    device_type: DeviceType
    status: DeviceStatus = DeviceStatus.ONLINE
    capabilities: DeviceCapabilities = Field(default_factory=DeviceCapabilities)
    paired_by_user_id: str = "default_user"
    token_hash: str = ""
    created_at: float = Field(default_factory=time.time)
    last_seen_at: float = Field(default_factory=time.time)
    allowed_applications: List[str] = Field(default_factory=lambda: ["*"])
    granted_permissions: List[str] = Field(default_factory=lambda: ["read", "act"])


class ActionRequest(BaseModel):
    action_id: str = Field(default_factory=lambda: f"act-{uuid.uuid4().hex[:10]}")
    device_id: str
    action_type: ActionType
    target_app: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    risk_category: RiskCategory = RiskCategory.CATEGORY_A_LOW
    requires_approval: bool = False
    reauth_token: Optional[str] = None
    created_at: float = Field(default_factory=time.time)


class ApprovalRequest(BaseModel):
    approval_id: str = Field(default_factory=lambda: f"appr-{uuid.uuid4().hex[:10]}")
    action_id: str
    device_id: str
    user_id: str = "default_user"
    action_type: ActionType
    risk_category: RiskCategory
    target_app: str
    summary: str
    consequences: str
    affected_content: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    expires_at: float = Field(default_factory=lambda: time.time() + 600)  # 10 min default TTL
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_at: Optional[float] = None
    decision_notes: Optional[str] = None


class VerificationResult(BaseModel):
    action_id: str
    level: VerificationLevel = VerificationLevel.ATTEMPTED
    verified: bool = False
    evidence: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class ActionResult(BaseModel):
    action_id: str
    device_id: str
    action_type: ActionType
    success: bool
    status: str = "completed"
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    verification: Optional[VerificationResult] = None
    duration_ms: float = 0.0
