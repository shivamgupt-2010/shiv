"""
ShivAI V2 Universal Orchestration and Planning API Router.
Exposes intent classification across 17 domains and DAG execution plan synthesis.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.orchestration.intent import intent_classifier, IntentClassification
from core.orchestration.planner import task_planner, ExecutionPlan
from security.shiv_auth import get_current_user, UserContext

router = APIRouter(prefix="/v2/orchestration", tags=["Orchestration & Planning"])


class ClassifyRequest(BaseModel):
    prompt: str = Field(..., description="User prompt or task brief to classify")


class PlanRequest(BaseModel):
    goal: str = Field(..., description="High-level goal or project request to decompose")


@router.post("/classify", response_model=IntentClassification)
def classify_intent(
    req: ClassifyRequest,
    user: UserContext = Depends(get_current_user),
):
    """Classifies user input across 17 distinct capability categories with multi-intent support."""
    return intent_classifier.classify(req.prompt)


@router.post("/plan", response_model=ExecutionPlan)
def generate_execution_plan(
    req: PlanRequest,
    user: UserContext = Depends(get_current_user),
):
    """Synthesizes an ordered, dependency-aware DAG execution plan with specialist agent assignments."""
    return task_planner.plan(req.goal)
