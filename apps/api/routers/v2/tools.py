"""
ShivAI V2 Tool Execution & Catalog Endpoints.
Exposes GET /v2/tools and POST /v2/tools/execute.
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, status, HTTPException
from pydantic import BaseModel, Field

from apps.api.dependencies import get_current_user_context, UserContext, rate_limit_middleware_check
from core.tools.registry import tool_registry

router = APIRouter(tags=["V2 Tools & Function Calling"])


class ToolExecuteRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the tool to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Input parameters for the tool")


class ToolExecuteResponse(BaseModel):
    tool_name: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None


@router.get(
    "/v2/tools",
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/api/v2/tools",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_tools() -> Dict[str, Any]:
    """Lists all available tools, their schemas, and required permissions."""
    defs = tool_registry.list_definitions()
    return {
        "count": len(defs),
        "tools": [
            {
                "name": d.name,
                "description": d.description,
                "required_permission": d.required_permission,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required,
                        "default": p.default,
                    }
                    for p in d.parameters
                ],
            }
            for d in defs
        ],
    }


@router.post(
    "/v2/tools/execute",
    response_model=ToolExecuteResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.post(
    "/api/v2/tools/execute",
    response_model=ToolExecuteResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def execute_tool(
    req: ToolExecuteRequest,
    user: UserContext = Depends(get_current_user_context),
) -> ToolExecuteResponse:
    """Executes a registered tool within security constraints."""
    tool = tool_registry.get_tool(req.tool_name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{req.tool_name}' not found.",
        )

    res = await tool_registry.execute_tool(req.tool_name, req.arguments)
    success = res.get("success", False)
    return ToolExecuteResponse(
        tool_name=req.tool_name,
        success=success,
        result=res if success else None,
        error=res.get("error") if not success else None,
    )
