"""
ShivAI V2 Multi-Agent Orchestration Endpoints.
Exposes GET /v2/agents and POST /v2/agents/execute.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from apps.api.dependencies import get_current_user_context, UserContext, rate_limit_middleware_check
from core.agents.v2.orchestrator import multi_agent_orchestrator, MultiAgentExecutionResult
from core.agents.v2.roles import SPECIALIZED_AGENTS

router = APIRouter(tags=["V2 Multi-Agent Orchestration"])


class AgentExecutionRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=5000, description="The complex mission or goal to accomplish")
    preferred_agents: Optional[List[str]] = Field(default=None, description="Optional subset of agents to invoke")


@router.get(
    "/v2/agents",
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/api/v2/agents",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_available_agents():
    """Lists all registered specialist agent roles and their capability definitions."""
    return {
        "count": len(SPECIALIZED_AGENTS),
        "agents": [
            {
                "role_id": role.role_id,
                "name": role.name,
                "description": role.description,
                "capabilities": role.required_capabilities,
                "assigned_tools": role.assigned_tools,
            }
            for role in SPECIALIZED_AGENTS.values()
        ],
    }


@router.post(
    "/v2/agents/execute",
    response_model=MultiAgentExecutionResult,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.post(
    "/api/v2/agents/execute",
    response_model=MultiAgentExecutionResult,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def execute_multi_agent_task(
    req: AgentExecutionRequest,
    user: UserContext = Depends(get_current_user_context),
) -> MultiAgentExecutionResult:
    """
    Decomposes and executes a complex goal using a coordinated team of autonomous specialist agents.
    """
    return await multi_agent_orchestrator.execute_task(
        goal=req.goal,
        user_id=user.user_id,
        preferred_agents=req.preferred_agents,
    )
