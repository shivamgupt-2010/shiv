"""
Persistent Memory router.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.dependencies import get_db, get_current_user_id
from core.memory.memory_manager import MemoryManager

router = APIRouter(prefix="/api/v1/memory", tags=["Memory"])


class MemoryCreateRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=150, description="Unique key for the fact or preference")
    value: str = Field(..., min_length=1, description="Content of the memory fact")
    category: Optional[str] = Field(default="general", description="Category (preference, fact, profile, system)")
    importance: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)


class MemoryResponse(BaseModel):
    id: str
    key: str
    value: str
    category: str
    importance: float
    confidence: float
    source: str
    created_at: str


@router.get("", response_model=List[MemoryResponse])
async def list_memories(
    category: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 50,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    mgr = MemoryManager(session)
    memories = await mgr.recall(user_id=user_id, query=query, category=category, limit=limit)
    return [
        MemoryResponse(
            id=m.id,
            key=m.key,
            value=m.value,
            category=m.category,
            importance=m.importance,
            confidence=m.confidence,
            source=m.source,
            created_at=m.created_at.isoformat(),
        )
        for m in memories
    ]


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def remember_fact(
    body: MemoryCreateRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    mgr = MemoryManager(session)
    mem = await mgr.remember(
        user_id=user_id,
        key=body.key,
        value=body.value,
        category=body.category or "general",
        importance=body.importance if body.importance is not None else 0.5,
    )
    return MemoryResponse(
        id=mem.id,
        key=mem.key,
        value=mem.value,
        category=mem.category,
        importance=mem.importance,
        confidence=mem.confidence,
        source=mem.source,
        created_at=mem.created_at.isoformat(),
    )


@router.delete("/{memory_id}", status_code=status.HTTP_200_OK)
async def forget_memory(
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    mgr = MemoryManager(session)
    success = await mgr.forget(user_id=user_id, memory_id=memory_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Memory not found."}},
        )
    return {"status": "success", "message": "Memory removed."}
