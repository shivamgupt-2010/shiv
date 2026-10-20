"""
SHIV AI — Digital Work Automation API Router (v2)
Exposes endpoints for Social Media Strategy, Email Operations, Form Filling,
Creative App Scripting, and Recurring Automation Scheduling.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.automation.communication import CommunicationAgent
from core.automation.creative import CreativeAppOperator
from core.automation.forms import FormAutomationAgent
from core.automation.scheduler import ScheduledWorkflow, get_automation_scheduler
from core.automation.social_media import SocialMediaOperationsAgent
from security.shiv_auth import get_current_user

logger = logging.getLogger("shivai.api.v2.automation")

router = APIRouter(prefix="/v2/automation", tags=["automation"])


# --- Social Media Payloads ---
class SocialCalendarPayload(BaseModel):
    goal: str = "Brand Awareness & Launch"
    platforms: Optional[List[str]] = None
    days: int = 7


class SocialDraftPayload(BaseModel):
    platform: str = "twitter"
    topic: str
    tone: str = "engaging"
    media_url: Optional[str] = None


class SocialPublishRequestPayload(BaseModel):
    draft_id: str
    platform: str
    caption: str
    media_url: Optional[str] = None


class SocialPublishExecutePayload(BaseModel):
    action_id: str
    approval_id: str
    platform: str
    caption: str


class SocialTriagePayload(BaseModel):
    comments: List[Dict[str, str]]


# --- Email Payloads ---
class EmailSummaryPayload(BaseModel):
    messages: List[Dict[str, str]]


class EmailDraftPayload(BaseModel):
    recipient: str
    subject: str
    context_notes: str
    tone: str = "professional"


class EmailSendRequestPayload(BaseModel):
    draft_id: str
    recipient: str
    subject: str
    body: str
    attachments: Optional[List[str]] = None


class EmailSendExecutePayload(BaseModel):
    action_id: str
    approval_id: str
    recipient: str
    subject: str
    body: str


# --- Form Payloads ---
class FormExtractPayload(BaseModel):
    document_text: str


class FormSubmitRequestPayload(BaseModel):
    form_name: str
    destination_url: str
    fields: Dict[str, Any]
    is_binding: bool = False


# --- Creative Payloads ---
class CreativeRenderPayload(BaseModel):
    operation: str = "trim"
    params: Dict[str, Any] = Field(default_factory=dict)


# --- Schedule Payloads ---
class WorkflowTogglePayload(BaseModel):
    enabled: bool


# --- Social Media Endpoints ---
@router.post("/social/calendar")
async def generate_social_calendar(
    payload: SocialCalendarPayload,
    current_user: Any = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    return SocialMediaOperationsAgent.generate_content_calendar(
        campaign_goal=payload.goal,
        platforms=payload.platforms,
        days=payload.days,
    )


@router.post("/social/draft")
async def draft_social_post(
    payload: SocialDraftPayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    return SocialMediaOperationsAgent.draft_post(
        platform=payload.platform,
        topic=payload.topic,
        tone=payload.tone,
        media_url=payload.media_url,
    )


@router.post("/social/publish/request")
async def request_social_publish(
    payload: SocialPublishRequestPayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    user_id = getattr(current_user, "user_id", "default_user")
    action = SocialMediaOperationsAgent.request_publication(
        draft_id=payload.draft_id,
        platform=payload.platform,
        caption=payload.caption,
        media_url=payload.media_url,
        user_id=user_id,
    )
    return {
        "action_id": action.action_id,
        "status": "pending_approval",
        "requires_approval": True,
        "summary": f"Publication request registered for {payload.platform}. Please approve in Command Center.",
    }


@router.post("/social/publish/execute")
async def execute_social_publish(
    payload: SocialPublishExecutePayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    user_id = getattr(current_user, "user_id", "default_user")
    from core.devices.types import ActionRequest, ActionType, RiskCategory
    action = ActionRequest(
        action_id=payload.action_id,
        device_id="social-publisher",
        action_type=ActionType.PUBLISH_POST,
        params={"platform": payload.platform, "caption": payload.caption},
        risk_category=RiskCategory.CATEGORY_B_CONSEQUENTIAL,
    )
    try:
        res = SocialMediaOperationsAgent.execute_publish(
            action=action,
            approval_id=payload.approval_id,
            user_id=user_id,
        )
        return res.model_dump()
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/social/triage")
async def triage_comments(
    payload: SocialTriagePayload,
    current_user: Any = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    return SocialMediaOperationsAgent.triage_comments(payload.comments)


# --- Email Endpoints ---
@router.post("/email/summarize")
async def summarize_email_thread(
    payload: EmailSummaryPayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    return CommunicationAgent.summarize_thread(payload.messages)


@router.post("/email/draft")
async def draft_email(
    payload: EmailDraftPayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    return CommunicationAgent.draft_email_reply(
        recipient=payload.recipient,
        subject=payload.subject,
        context_notes=payload.context_notes,
        tone=payload.tone,
    )


@router.post("/email/send/request")
async def request_send_email(
    payload: EmailSendRequestPayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    user_id = getattr(current_user, "user_id", "default_user")
    action = CommunicationAgent.request_send_email(
        draft_id=payload.draft_id,
        recipient=payload.recipient,
        subject=payload.subject,
        body=payload.body,
        attachments=payload.attachments,
        user_id=user_id,
    )
    return {
        "action_id": action.action_id,
        "status": "pending_approval",
        "requires_approval": True,
        "summary": f"Send email request to '{payload.recipient}' submitted for approval.",
    }


# --- Form Endpoints ---
@router.post("/forms/extract")
async def extract_form_fields(
    payload: FormExtractPayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    return FormAutomationAgent.extract_fields(payload.document_text)


@router.post("/forms/submit/request")
async def request_form_submit(
    payload: FormSubmitRequestPayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    user_id = getattr(current_user, "user_id", "default_user")
    action = FormAutomationAgent.prepare_form_submission(
        form_name=payload.form_name,
        destination_url=payload.destination_url,
        fields=payload.fields,
        is_binding_or_financial=payload.is_binding,
        user_id=user_id,
    )
    return {
        "action_id": action.action_id,
        "status": "pending_approval",
        "risk_category": action.risk_category.value,
        "summary": f"Form '{payload.form_name}' submission ticket created.",
    }


# --- Creative Endpoints ---
@router.post("/creative/execute")
async def execute_creative(
    payload: CreativeRenderPayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    res = CreativeAppOperator.execute_creative_render(
        operation=payload.operation,
        params=payload.params,
    )
    return res.model_dump()


# --- Recurring Automation Schedules ---
@router.get("/schedules", response_model=List[ScheduledWorkflow])
async def list_schedules(
    current_user: Any = Depends(get_current_user),
) -> List[ScheduledWorkflow]:
    return get_automation_scheduler().list_workflows()


@router.post("/schedules/{workflow_id}/toggle")
async def toggle_schedule(
    workflow_id: str,
    payload: WorkflowTogglePayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        wf = get_automation_scheduler().toggle_workflow(workflow_id, payload.enabled)
        return wf.model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="Scheduled workflow not found")


@router.post("/schedules/{workflow_id}/trigger")
async def trigger_schedule_now(
    workflow_id: str,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        return get_automation_scheduler().trigger_now(workflow_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Scheduled workflow not found")
