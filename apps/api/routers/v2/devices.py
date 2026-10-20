"""
SHIV AI — Device Operations & Governance API Router (v2)
Exposes device pairing, capability discovery, screen observation,
permission-gated action execution, approval management, and emergency stop controls.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from core.devices.adapters import get_adapter_for_device
from core.devices.emergency_stop import get_emergency_stop
from core.devices.permissions import get_device_permission_manager
from core.devices.registry import get_device_registry
from core.devices.types import (
    ActionRequest,
    ActionResult,
    ActionType,
    ApprovalRequest,
    ApprovalStatus,
    DeviceCapabilities,
    DeviceRecord,
    DeviceStatus,
    DeviceType,
    RiskCategory,
    ScreenObservation,
    VerificationLevel,
)
from core.devices.verification import TaskVerificationEngine
from security.shiv_auth import get_current_user

logger = logging.getLogger("shivai.api.v2.devices")

router = APIRouter(prefix="/v2/devices", tags=["devices"])


class PairRequestPayload(BaseModel):
    name: str = "My Device"
    device_type: DeviceType = DeviceType.WINDOWS
    ttl_seconds: int = 300


class PairCompletePayload(BaseModel):
    pairing_code: str
    capabilities: Optional[DeviceCapabilities] = None


class ActionDispatchPayload(BaseModel):
    action_type: ActionType
    target_app: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    reauth_token: Optional[str] = None


class ApprovalDecisionPayload(BaseModel):
    approved: bool
    notes: Optional[str] = None


class EmergencyStopPayload(BaseModel):
    reason: str = "User initiated emergency stop"


@router.post("/pair/request")
async def request_pairing(
    payload: PairRequestPayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generates a short-lived pairing code for device enrollment."""
    user_id = getattr(current_user, "user_id", "default_user")
    registry = get_device_registry()
    return registry.generate_pairing_code(
        user_id=user_id,
        name=payload.name,
        device_type=payload.device_type,
        ttl_seconds=payload.ttl_seconds,
    )


@router.post("/pair/complete")
async def complete_pairing(
    payload: PairCompletePayload,
) -> Dict[str, Any]:
    """Exchanges pairing code for permanent device credentials."""
    registry = get_device_registry()
    try:
        return registry.complete_pairing(
            pairing_code=payload.pairing_code,
            capabilities=payload.capabilities,
        )
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))


@router.get("", response_model=List[DeviceRecord])
async def list_devices(
    current_user: Any = Depends(get_current_user),
) -> List[DeviceRecord]:
    """Lists all enrolled devices accessible to the current user."""
    user_id = getattr(current_user, "user_id", "default_user")
    return get_device_registry().list_devices(user_id=user_id)


@router.get("/{device_id}", response_model=DeviceRecord)
async def get_device(
    device_id: str,
    current_user: Any = Depends(get_current_user),
) -> DeviceRecord:
    dev = get_device_registry().get_device(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
    return dev


@router.post("/{device_id}/revoke")
async def revoke_device(
    device_id: str,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    user_id = getattr(current_user, "user_id", "default_user")
    success = get_device_registry().revoke_device(device_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"device_id": device_id, "revoked": True}


@router.post("/{device_id}/observe", response_model=ScreenObservation)
async def observe_device(
    device_id: str,
    include_screenshot: bool = Query(False),
    current_user: Any = Depends(get_current_user),
) -> ScreenObservation:
    dev = get_device_registry().get_device(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    adapter = get_adapter_for_device(dev)
    return adapter.observe(include_screenshot=include_screenshot)


@router.post("/{device_id}/action")
async def dispatch_action(
    device_id: str,
    payload: ActionDispatchPayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Evaluates action through the 3-Tier Policy Engine:
    - If Category A: executes immediately and verifies output.
    - If Category B or C: creates an approval ticket and returns 202 Accepted.
    """
    user_id = getattr(current_user, "user_id", "default_user")
    dev = get_device_registry().get_device(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")

    action = ActionRequest(
        device_id=device_id,
        action_type=payload.action_type,
        target_app=payload.target_app,
        params=payload.params,
        reauth_token=payload.reauth_token,
    )

    pm = get_device_permission_manager()
    can_execute, approval, rationale = pm.evaluate_action(dev, action, user_id=user_id)

    if not can_execute:
        return {
            "action_id": action.action_id,
            "status": "pending_approval",
            "risk_category": action.risk_category.value,
            "rationale": rationale,
            "approval_ticket": approval.model_dump() if approval else None,
        }

    # Execute action via adapter
    adapter = get_adapter_for_device(dev)
    try:
        output = adapter.execute(action)
        verification = TaskVerificationEngine.verify_action(action, output)
        result = ActionResult(
            action_id=action.action_id,
            device_id=device_id,
            action_type=action.action_type,
            success=True,
            status="completed",
            output=output,
            verification=verification,
        )
        return result.model_dump()
    except Exception as e:
        logger.error(f"Error executing action {action.action_id}: {e}")
        return ActionResult(
            action_id=action.action_id,
            device_id=device_id,
            action_type=action.action_type,
            success=False,
            status="failed",
            error=str(e),
        ).model_dump()


@router.get("/approvals/pending", response_model=List[ApprovalRequest])
async def list_pending_approvals(
    current_user: Any = Depends(get_current_user),
) -> List[ApprovalRequest]:
    user_id = getattr(current_user, "user_id", "default_user")
    return get_device_permission_manager().get_pending_approvals(user_id=user_id)


@router.post("/approvals/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    payload: ApprovalDecisionPayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    user_id = getattr(current_user, "user_id", "default_user")
    try:
        appr = get_device_permission_manager().decide_approval(
            approval_id=approval_id,
            approved=payload.approved,
            user_id=user_id,
            decision_notes=payload.notes,
        )
        return appr.model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="Approval ticket not found")
    except TimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))


@router.get("/emergency-stop/status")
async def emergency_stop_status() -> Dict[str, Any]:
    return get_emergency_stop().details


@router.post("/emergency-stop/trigger")
async def trigger_emergency_stop(
    payload: EmergencyStopPayload,
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    user_id = getattr(current_user, "user_id", "default_user")
    return get_emergency_stop().trigger(user_id=user_id, reason=payload.reason)


@router.post("/emergency-stop/reset")
async def reset_emergency_stop(
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    user_id = getattr(current_user, "user_id", "default_user")
    return get_emergency_stop().reset(user_id=user_id)
