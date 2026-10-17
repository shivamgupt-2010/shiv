"""
ShivAI V2 Web Research Endpoint.
Exposes POST /v2/research and POST /api/v2/research.
"""
from typing import Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from apps.api.dependencies import get_current_user_context, UserContext, rate_limit_middleware_check
from core.research.researcher import researcher, ResearchReport

router = APIRouter(tags=["V2 Web Research"])


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000, description="Research topic or question")
    depth: str = Field(default="quick", description="Research depth: 'quick' (single query) or 'deep' (multi-query cross verification)")
    max_sources: int = Field(default=5, ge=1, le=10, description="Maximum number of sources to consult")


@router.post(
    "/v2/research",
    response_model=ResearchReport,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.post(
    "/api/v2/research",
    response_model=ResearchReport,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def conduct_web_research(
    req: ResearchRequest,
    user: UserContext = Depends(get_current_user_context),
) -> ResearchReport:
    """
    Executes autonomous real-time web research:
    Gathers multi-source evidence, sanitizes untrusted content, and returns a verified report with citations.
    """
    return await researcher.conduct_research(
        query=req.query,
        depth=req.depth,
        max_sources=req.max_sources,
        user_id=user.user_id,
    )
