"""
SHIV AI — Recurring Background Automation Scheduler
Manages user-authorized recurring workflows, cron schedules, resource boundaries,
and provides single-click emergency disable controls.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.devices.types import ActionType

logger = logging.getLogger("shivai.automation.scheduler")


class ScheduledWorkflow(BaseModel):
    workflow_id: str = Field(default_factory=lambda: f"wf-{uuid.uuid4().hex[:8]}")
    name: str
    description: str = ""
    interval_seconds: int = 86400  # Default once daily
    authorized_device_id: str = "host-local-primary"
    action_type: ActionType
    params: Dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True
    approval_required: bool = True
    created_at: float = Field(default_factory=time.time)
    last_run_at: Optional[float] = None
    next_run_at: Optional[float] = None
    execution_count: int = 0


class AutomationScheduler:
    """Schedules and manages recurring automation tasks."""

    def __init__(self) -> None:
        self._workflows: Dict[str, ScheduledWorkflow] = {}
        self._execution_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

        # Seed standard recurring workflow presets
        self._seed_default_workflows()

    def _seed_default_workflows(self) -> None:
        presets = [
            ScheduledWorkflow(
                workflow_id="wf-weekly-social-calendar",
                name="Weekly Content Calendar Generator",
                description="Generates draft social media calendar and posts every Monday.",
                interval_seconds=604800,  # 7 days
                action_type=ActionType.PUBLISH_POST,
                params={"topic": "Weekly Product Milestones", "platforms": ["twitter", "linkedin"]},
                is_enabled=False,
                approval_required=True,
            ),
            ScheduledWorkflow(
                workflow_id="wf-daily-inbox-summary",
                name="Daily Executive Inbox Summary",
                description="Summarizes unanswered customer threads and drafts proposed replies.",
                interval_seconds=86400,  # 24 hours
                action_type=ActionType.READ_CONTENT,
                params={"target": "inbox", "urgency_filter": "high"},
                is_enabled=True,
                approval_required=True,
            ),
        ]
        for p in presets:
            p.next_run_at = time.time() + p.interval_seconds
            self._workflows[p.workflow_id] = p

    def register_workflow(self, workflow: ScheduledWorkflow) -> ScheduledWorkflow:
        with self._lock:
            workflow.next_run_at = time.time() + workflow.interval_seconds
            self._workflows[workflow.workflow_id] = workflow
        logger.info(f"Registered scheduled workflow: '{workflow.name}' ({workflow.workflow_id})")
        return workflow

    def list_workflows(self) -> List[ScheduledWorkflow]:
        with self._lock:
            return sorted(list(self._workflows.values()), key=lambda w: w.name)

    def get_workflow(self, workflow_id: str) -> Optional[ScheduledWorkflow]:
        with self._lock:
            return self._workflows.get(workflow_id)

    def toggle_workflow(self, workflow_id: str, enable: bool) -> ScheduledWorkflow:
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if not wf:
                raise KeyError(f"Workflow '{workflow_id}' not found")
            wf.is_enabled = enable
            if enable:
                wf.next_run_at = time.time() + wf.interval_seconds
            else:
                wf.next_run_at = None
        logger.info(f"Workflow '{workflow_id}' enabled={enable}")
        return wf

    def trigger_now(self, workflow_id: str) -> Dict[str, Any]:
        """Manually triggers a scheduled workflow run immediately."""
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if not wf:
                raise KeyError(f"Workflow '{workflow_id}' not found")
            wf.last_run_at = time.time()
            wf.next_run_at = time.time() + wf.interval_seconds
            wf.execution_count += 1

            record = {
                "execution_id": f"exec-{uuid.uuid4().hex[:8]}",
                "workflow_id": workflow_id,
                "workflow_name": wf.name,
                "action_type": wf.action_type.value,
                "triggered_at": time.time(),
                "status": "pending_approval" if wf.approval_required else "completed",
            }
            self._execution_history.append(record)

        return record


_scheduler_singleton = AutomationScheduler()


def get_automation_scheduler() -> AutomationScheduler:
    return _scheduler_singleton
