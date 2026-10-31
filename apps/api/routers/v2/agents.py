"""
ShivAI V2 Multi-Agent Orchestration & Dynamic Agent Forge Endpoints.
Exposes:
- GET /v2/agents: lists built-in and custom agents
- POST /v2/agents/execute: executes a goal across agents
- POST /v2/agents/custom: creates a new custom agent
- GET /v2/agents/custom: lists all custom agents
- PUT /v2/agents/custom/{agent_id}: updates a custom agent
- DELETE /v2/agents/custom/{agent_id}: deletes a custom agent
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from apps.api.dependencies import get_current_user_context, UserContext, rate_limit_middleware_check
from core.agents.v2.orchestrator import multi_agent_orchestrator, MultiAgentExecutionResult
from core.agents.v2.roles import SPECIALIZED_AGENTS
from core.agents.custom_agent_manager import custom_agent_manager, CustomAgentModel

router = APIRouter(tags=["V2 Multi-Agent Orchestration"])


class AgentExecutionRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=5000, description="The complex mission or goal to accomplish")
    preferred_agents: Optional[List[str]] = Field(default=None, description="Optional subset of agents to invoke")


class CreateCustomAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    purpose: str = Field(..., min_length=1, max_length=500)
    instructions: str = Field(..., min_length=1)
    key: Optional[str] = None
    required_capabilities: Optional[Dict[str, bool]] = None
    allowed_tools: Optional[List[str]] = None
    preferred_provider: Optional[str] = None


class UpdateCustomAgentRequest(BaseModel):
    name: Optional[str] = None
    purpose: Optional[str] = None
    instructions: Optional[str] = None
    required_capabilities: Optional[Dict[str, bool]] = None
    allowed_tools: Optional[List[str]] = None
    preferred_provider: Optional[str] = None


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
    builtins = [
        {
            "role_id": role.role_id,
            "name": role.name,
            "description": role.description,
            "capabilities": role.required_capabilities,
            "assigned_tools": role.assigned_tools,
            "is_custom": False,
        }
        for role in SPECIALIZED_AGENTS.values()
    ]
    customs = [
        {
            "role_id": a.agent_id,
            "name": a.name,
            "description": a.purpose,
            "capabilities": a.required_capabilities,
            "assigned_tools": a.allowed_tools,
            "is_custom": True,
            "key": a.key,
        }
        for a in custom_agent_manager.list_agents()
    ]
    return {
        "count": len(builtins) + len(customs),
        "agents": builtins + customs,
    }


@router.post(
    "/v2/agents/custom",
    response_model=CustomAgentModel,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.post(
    "/api/v2/agents/custom",
    response_model=CustomAgentModel,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def create_custom_agent(
    req: CreateCustomAgentRequest,
    user: UserContext = Depends(get_current_user_context),
):
    """Dynamically creates a new custom agent and mounts it into the runtime."""
    agent = custom_agent_manager.create_agent(
        name=req.name,
        purpose=req.purpose,
        instructions=req.instructions,
        key=req.key,
        required_capabilities=req.required_capabilities,
        allowed_tools=req.allowed_tools,
        preferred_provider=req.preferred_provider,
    )
    return agent


@router.get(
    "/v2/agents/custom",
    response_model=List[CustomAgentModel],
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/api/v2/agents/custom",
    response_model=List[CustomAgentModel],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_custom_agents():
    """Lists all user and AI created custom agents."""
    return custom_agent_manager.list_agents()


@router.put(
    "/v2/agents/custom/{agent_id}",
    response_model=CustomAgentModel,
    status_code=status.HTTP_200_OK,
)
@router.put(
    "/api/v2/agents/custom/{agent_id}",
    response_model=CustomAgentModel,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def update_custom_agent(
    agent_id: str,
    req: UpdateCustomAgentRequest,
    user: UserContext = Depends(get_current_user_context),
):
    """Updates an existing custom agent."""
    updated = custom_agent_manager.update_agent(
        agent_id=agent_id,
        name=req.name,
        purpose=req.purpose,
        instructions=req.instructions,
        required_capabilities=req.required_capabilities,
        allowed_tools=req.allowed_tools,
        preferred_provider=req.preferred_provider,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Custom agent '{agent_id}' not found")
    return updated


@router.delete(
    "/v2/agents/custom/{agent_id}",
    status_code=status.HTTP_200_OK,
)
@router.delete(
    "/api/v2/agents/custom/{agent_id}",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def delete_custom_agent(
    agent_id: str,
    user: UserContext = Depends(get_current_user_context),
):
    """Deletes a custom agent from disk and active runtime."""
    success = custom_agent_manager.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Custom agent '{agent_id}' not found")
    return {"status": "deleted", "agent_id": agent_id}


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
