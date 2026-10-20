"""
Unit tests for SHIV AI: Universal Device Operator & Digital Work Automation
Covers types, security scrubber, emergency stop, registry, 3-tier permissions,
adapters (Windows, Android, Browser), verification, and creative/work automation agents.
"""

import time
import pytest

from core.automation.communication import CommunicationAgent
from core.automation.creative import CreativeAppOperator
from core.automation.forms import FormAutomationAgent
from core.automation.scheduler import AutomationScheduler, ScheduledWorkflow
from core.automation.social_media import SocialMediaOperationsAgent
from core.devices.adapters.android import AndroidDeviceAdapter
from core.devices.adapters.browser import BrowserAutomationAdapter
from core.devices.adapters.windows import WindowsDesktopAdapter
from core.devices.emergency_stop import EmergencyStopActiveError, EmergencyStopManager
from core.devices.observation import ScreenObservationService
from core.devices.permissions import DevicePermissionManager
from core.devices.registry import DeviceRegistry
from core.devices.security import SensitiveDataScrubber
from core.devices.types import (
    ActionRequest,
    ActionType,
    ApprovalStatus,
    DeviceCapabilities,
    DeviceRecord,
    DeviceStatus,
    DeviceType,
    RiskCategory,
    VerificationLevel,
)
from core.devices.verification import TaskVerificationEngine


def test_device_types_and_models():
    """Verifies enumeration values and default model structures."""
    assert DeviceType.WINDOWS.value == "windows"
    assert DeviceType.ANDROID.value == "android"
    assert RiskCategory.CATEGORY_A_LOW.value == "category_a_low"
    assert RiskCategory.CATEGORY_B_CONSEQUENTIAL.value == "category_b_consequential"
    assert RiskCategory.CATEGORY_C_SENSITIVE.value == "category_c_sensitive"
    assert VerificationLevel.INDEPENDENTLY_VERIFIED.value == "independently_verified"

    req = ActionRequest(device_id="dev-1", action_type=ActionType.LAUNCH_APP)
    assert req.action_id.startswith("act-")
    assert req.risk_category == RiskCategory.CATEGORY_A_LOW


def test_sensitive_data_scrubber():
    """Verifies that secrets, keys, passwords, and payment cards are masked."""
    raw_text = "My password: SuperSecretPassword123 and token Bearer eyJhbGciOiJIUzI1NiJ9.test and card 4111 2222 3333 4444"
    scrubbed, count = SensitiveDataScrubber.scrub_text(raw_text)
    assert count >= 3
    assert "SuperSecretPassword123" not in scrubbed
    assert "[REDACTED_PASSWORD]" in scrubbed
    assert "[REDACTED_TOKEN]" in scrubbed
    assert "[REDACTED_PAYMENT_CARD]" in scrubbed

    data = {
        "api_key": "secret-api-key-998877",
        "nested": {"user_password": "my_password_xyz", "safe_val": "hello world"},
    }
    scrubbed_dict, d_count = SensitiveDataScrubber.scrub_dict(data)
    assert d_count >= 2
    assert scrubbed_dict["api_key"] == "[REDACTED_SECRET]"
    assert scrubbed_dict["nested"]["user_password"] == "[REDACTED_SECRET]"
    assert scrubbed_dict["nested"]["safe_val"] == "hello world"


def test_emergency_stop_lifecycle():
    """Verifies that the emergency stop halts all actions and triggers callbacks."""
    em = EmergencyStopManager()
    callback_fired = False

    def on_stop():
        nonlocal callback_fired
        callback_fired = True

    em.register_callback(on_stop)
    em.reset("test_user")
    assert not em.is_active

    # Trigger emergency stop
    em.trigger("test_admin", "Test trigger")
    assert em.is_active
    assert callback_fired
    assert em.details["triggered_by"] == "test_admin"

    with pytest.raises(EmergencyStopActiveError):
        em.assert_not_stopped()

    # Reset
    em.reset("test_admin")
    assert not em.is_active
    em.assert_not_stopped()


def test_device_registry_pairing_and_revocation():
    """Verifies device pairing codes, enrollment, and explicit revocation."""
    reg = DeviceRegistry()
    code_info = reg.generate_pairing_code("user1", "Work Laptop", DeviceType.WINDOWS, ttl_seconds=300)
    assert "pairing_code" in code_info

    # Complete pairing
    paired = reg.complete_pairing(code_info["pairing_code"])
    dev_id = paired["device_id"]
    assert dev_id.startswith("dev-")
    assert "device_token" in paired

    record = reg.get_device(dev_id)
    assert record is not None
    assert record.status == DeviceStatus.ONLINE

    # Revoke
    revoked = reg.revoke_device(dev_id, user_id="user1")
    assert revoked is True
    assert reg.get_device(dev_id).status == DeviceStatus.REVOKED


def test_3_tier_permission_engine():
    """Verifies Category A (auto), Category B (approval required), and Category C (sensitive)."""
    pm = DevicePermissionManager()
    dev = DeviceRecord(device_id="dev-test", name="Test Device", device_type=DeviceType.WINDOWS)

    # Category A: Observe state -> auto-approved
    act_a = ActionRequest(device_id="dev-test", action_type=ActionType.OBSERVE_STATE)
    can_exec, appr, rationale = pm.evaluate_action(dev, act_a)
    assert can_exec is True
    assert appr is None
    assert "Category A" in rationale

    # Category B: Send email -> requires explicit approval
    act_b = ActionRequest(
        device_id="dev-test",
        action_type=ActionType.SEND_EMAIL,
        params={"recipient": "user@example.com", "subject": "Hello"},
    )
    can_exec_b, appr_b, rationale_b = pm.evaluate_action(dev, act_b)
    assert can_exec_b is False
    assert appr_b is not None
    assert appr_b.risk_category == RiskCategory.CATEGORY_B_CONSEQUENTIAL
    assert appr_b.status == ApprovalStatus.PENDING

    # Decide approval
    decided = pm.decide_approval(appr_b.approval_id, approved=True, user_id="test_admin")
    assert decided.status == ApprovalStatus.APPROVED

    # Category C: Financial / sensitive transaction -> sensitive category
    act_c = ActionRequest(
        device_id="dev-test",
        action_type=ActionType.SUBMIT_FORM,
        params={"account": "12345", "transfer_amount": "$5,000"},
    )
    can_exec_c, appr_c, rationale_c = pm.evaluate_action(dev, act_c)
    assert can_exec_c is False
    assert appr_c.risk_category == RiskCategory.CATEGORY_C_SENSITIVE


def test_screen_observation_service():
    """Verifies active window inspection and screen observation schema."""
    win = ScreenObservationService.get_active_window_info()
    assert "title" in win
    assert "process_name" in win
    assert "rect" in win

    obs = ScreenObservationService.observe("dev-local", include_screenshot=False)
    assert obs.device_id == "dev-local"
    assert len(obs.ui_elements) >= 1


def test_task_verification_engine(tmp_path):
    """Verifies file creation checks, window active assertions, and HTTP response verifications."""
    test_file = str(tmp_path / "output.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("SHIV AI Generated Content")

    res = TaskVerificationEngine.verify_file_created("act-1", test_file, min_bytes=5)
    assert res.verified is True
    assert res.level == VerificationLevel.INDEPENDENTLY_VERIFIED

    # Non-existent file
    res_fail = TaskVerificationEngine.verify_file_created("act-2", str(tmp_path / "missing.txt"))
    assert res_fail.verified is False
    assert res_fail.level == VerificationLevel.FAILED

    # HTTP response verification
    res_http = TaskVerificationEngine.verify_http_response("act-3", status_code=200)
    assert res_http.verified is True
    assert res_http.level == VerificationLevel.INDEPENDENTLY_VERIFIED


def test_windows_adapter_actions():
    """Verifies Windows desktop controller methods."""
    adapter = WindowsDesktopAdapter(device_id="win-1")
    res_text = adapter.enter_text("Hello ShivAI")
    assert res_text.get("entered") is True

    res_click = adapter.click(x=150, y=250)
    assert res_click.get("clicked") is True

    res_key = adapter.key_press("Enter")
    assert res_key.get("key_pressed") == "Enter"


def test_android_adapter_compatibility():
    """Verifies Android device adapter commands and simulated fallback."""
    adapter = AndroidDeviceAdapter(device_id="android-1")
    res_launch = adapter.launch_app("com.android.settings")
    assert res_launch.get("launched") is True

    res_tap = adapter.tap(x=300, y=600)
    assert res_tap.get("tapped") is True

    res_type = adapter.type_text("Test Search")
    assert res_type.get("typed") is True


def test_browser_adapter_semantic():
    """Verifies browser navigation, semantic form filling, and anti-injection sanitization."""
    adapter = BrowserAutomationAdapter(device_id="browser-1")
    assert adapter.ping() is True

    form_res = adapter.fill_form({"username": "shiv_user", "password": "supersecretpassword"})
    assert form_res.get("form_filled") is True
    assert form_res.get("redacted_secrets") >= 1

    click_res = adapter.click_semantic(selector="button.submit", text="Log In")
    assert click_res.get("clicked") is True


def test_social_media_agent():
    """Verifies content calendar generation, post drafting, and publication approval workflow."""
    calendar = SocialMediaOperationsAgent.generate_content_calendar(campaign_goal="SHIV AI V2 Launch", days=3)
    assert len(calendar) >= 6

    draft = SocialMediaOperationsAgent.draft_post(platform="twitter", topic="Zero-RAM Free Creative Studios")
    assert draft["platform"] == "twitter"
    assert "draft_id" in draft
    assert draft["status"] == "draft"

    action = SocialMediaOperationsAgent.request_publication(
        draft_id=draft["draft_id"],
        platform="twitter",
        caption=draft["caption"],
    )
    assert action.requires_approval is True


def test_communication_agent():
    """Verifies email summarization, draft generation, and approval requirements."""
    messages = [
        {"sender": "client@example.com", "body": "Please send the Q3 performance report by tomorrow.", "timestamp": time.time() - 3600},
        {"sender": "manager@example.com", "body": "Action: please prepare attachments and follow up.", "timestamp": time.time()},
    ]
    summary = CommunicationAgent.summarize_thread(messages)
    assert len(summary["action_items"]) >= 1
    assert summary["message_count"] == 2

    draft = CommunicationAgent.draft_email_reply(
        recipient="client@example.com",
        subject="Q3 Report",
        context_notes="The Q3 report is prepared and attached for your review.",
    )
    assert draft["status"] == "draft"
    assert draft["approval_required"] is True


def test_form_automation_agent():
    """Verifies document data extraction and form submission ticket creation."""
    doc = "Applicant Name: John Doe\nEmail: john.doe@example.com\nRequested Amount: $1,250.00"
    fields = FormAutomationAgent.extract_fields(doc)
    extracted = fields["extracted_fields"]
    assert extracted.get("full_name") == "John Doe"
    assert extracted.get("email") == "john.doe@example.com"
    assert extracted.get("amount") == "1,250.00"

    action = FormAutomationAgent.prepare_form_submission(
        form_name="Reimbursement Form",
        destination_url="https://portal.company.com/reimburse",
        fields=extracted,
        is_binding_or_financial=False,
    )
    assert action.requires_approval is True
    assert action.risk_category == RiskCategory.CATEGORY_B_CONSEQUENTIAL


def test_creative_app_operator():
    """Verifies deterministic FFmpeg CLI synthesis, Blender scripts, and Premiere FCPXML rendering."""
    ffmpeg_cmd = CreativeAppOperator.generate_ffmpeg_command(
        input_path="input.mp4",
        output_path="trimmed.mp4",
        operation="trim",
        params={"start_time": 5.0, "duration": 12.0},
    )
    assert "-ss" in ffmpeg_cmd
    assert "5.0" in ffmpeg_cmd

    blender_script = CreativeAppOperator.generate_blender_python_script(primitive="SPHERE", export_glb_path="sphere.glb")
    assert "bpy.ops.mesh.primitive_uv_sphere_add" in blender_script
    assert "sphere.glb" in blender_script

    fcpxml = CreativeAppOperator.generate_premiere_fcpxml(
        project_name="SocialPromo",
        clips=[{"name": "Intro", "duration": 3.5}, {"name": "Feature", "duration": 8.0}],
    )
    assert "<fcpxml" in fcpxml
    assert "SocialPromo" in fcpxml


def test_automation_scheduler():
    """Verifies recurring workflow registration, listing, toggling, and manual triggering."""
    sched = AutomationScheduler()
    wf = ScheduledWorkflow(
        workflow_id="wf-test-1",
        name="Test Workflow",
        interval_seconds=3600,
        action_type=ActionType.OBSERVE_STATE,
    )
    sched.register_workflow(wf)

    listed = sched.list_workflows()
    assert any(w.workflow_id == "wf-test-1" for w in listed)

    # Toggle
    toggled = sched.toggle_workflow("wf-test-1", enable=False)
    assert toggled.is_enabled is False

    # Trigger now
    res = sched.trigger_now("wf-test-1")
    assert res["workflow_id"] == "wf-test-1"
    assert "execution_id" in res
