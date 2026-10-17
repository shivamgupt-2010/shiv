"""
ShivAI V2 Memory Inspection & Management Endpoints.
Allows users to view, create, edit, and delete their stored memories and preferences.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, status, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db, get_current_user_context, UserContext, rate_limit_middleware_check
from core.memory.service import HierarchicalMemoryService
from services.shiv_db_service import shiv_db_service

router = APIRouter(tags=["V2 Memory & Personalization"])


class CreateMemoryRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=150, description="Memory label/key (e.g. 'preferred_language')")
    value: str = Field(..., min_length=1, max_length=5000, description="Memory content/fact")
    category: str = Field(default="fact", description="Category: preference, fact, goal, project, general")
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class UpdateMemoryRequest(BaseModel):
    value: Optional[str] = Field(default=None, max_length=5000)
    category: Optional[str] = Field(default=None, max_length=50)
    importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_active: Optional[bool] = Field(default=None)


class MemoryResponse(BaseModel):
    id: str
    user_id: str
    key: str
    value: str
    category: str
    importance: float
    confidence: float
    source: str
    is_active: bool


@router.get(
    "/v2/memory",
    response_model=List[MemoryResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.get(
    "/api/v2/memory",
    response_model=List[MemoryResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def list_memories(
    category: Optional[str] = None,
    limit: int = 50,
    user: UserContext = Depends(get_current_user_context),
    session: AsyncSession = Depends(get_db),
):
    """Lists all stored memories and preferences for the authenticated user."""
    service = HierarchicalMemoryService(session)
    memories = await service.list_user_memories(
        user_id=user.user_id,
        category=category,
        limit=min(limit, 100),
    )
    return [
        MemoryResponse(
            id=m.id,
            user_id=m.user_id,
            key=m.key,
            value=m.value,
            category=m.category,
            importance=m.importance,
            confidence=m.confidence,
            source=m.source,
            is_active=m.is_active,
        )
        for m in memories
    ]


@router.post(
    "/v2/memory",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.post(
    "/api/v2/memory",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def create_memory(
    req: CreateMemoryRequest,
    user: UserContext = Depends(get_current_user_context),
    session: AsyncSession = Depends(get_db),
):
    """Creates or updates a persistent fact or user preference."""
    service = HierarchicalMemoryService(session)
    mem = await service.store_user_memory(
        user_id=user.user_id,
        key=req.key,
        value=req.value,
        category=req.category,
        importance=req.importance,
    )
    if not mem:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Memory rejected: content contains sensitive credentials or invalid format.",
        )

    # Background cloud sync to SHIV DB Data Fabric
    try:
        import asyncio
        asyncio.create_task(
            shiv_db_service.create_record(
                collection="memories",
                data={
                    "id": mem.id,
                    "key": mem.key,
                    "value": mem.value,
                    "category": mem.category,
                    "importance": mem.importance,
                },
                user_id=user.user_id,
            )
        )
    except Exception:
        pass

    return MemoryResponse(
        id=mem.id,
        user_id=mem.user_id,
        key=mem.key,
        value=mem.value,
        category=mem.category,
        importance=mem.importance,
        confidence=mem.confidence,
        source=mem.source,
        is_active=mem.is_active,
    )


@router.patch(
    "/v2/memory/{memory_id}",
    response_model=MemoryResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.patch(
    "/api/v2/memory/{memory_id}",
    response_model=MemoryResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def update_memory(
    memory_id: str,
    req: UpdateMemoryRequest,
    user: UserContext = Depends(get_current_user_context),
    session: AsyncSession = Depends(get_db),
):
    """Allows user to edit or toggle active status of a stored memory item."""
    service = HierarchicalMemoryService(session)
    updated = await service.update_user_memory(
        user_id=user.user_id,
        memory_id=memory_id,
        new_value=req.value,
        new_category=req.category,
        new_importance=req.importance,
        is_active=req.is_active,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found or unauthorized.",
        )

    return MemoryResponse(
        id=updated.id,
        user_id=updated.user_id,
        key=updated.key,
        value=updated.value,
        category=updated.category,
        importance=updated.importance,
        confidence=updated.confidence,
        source=updated.source,
        is_active=updated.is_active,
    )


@router.delete(
    "/v2/memory/{memory_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.delete(
    "/api/v2/memory/{memory_id}",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def delete_memory(
    memory_id: str,
    user: UserContext = Depends(get_current_user_context),
    session: AsyncSession = Depends(get_db),
):
    """Permanently deactivates a memory item."""
    service = HierarchicalMemoryService(session)
    success = await service.delete_user_memory(user_id=user.user_id, memory_id=memory_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found or unauthorized.",
        )
    return {"deleted": True, "memory_id": memory_id}
