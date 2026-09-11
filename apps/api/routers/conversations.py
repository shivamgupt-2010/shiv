"""
Conversations management router.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.dependencies import get_db, get_current_user_id
from database.repositories.conversation_repo import ConversationRepository

router = APIRouter(prefix="/api/v1/conversations", tags=["Conversations"])


class ConversationCreate(BaseModel):
    title: Optional[str] = "New Conversation"
    system_instruction_override: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    created_at: str


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: Optional[List[MessageResponse]] = None


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(session)
    convs = await repo.list_user_conversations(user_id=user_id, limit=limit, offset=offset)
    return [
        ConversationResponse(
            id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
        for c in convs
    ]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(session)
    conv = await repo.get_by_id(conversation_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Conversation not found."}},
        )

    messages = [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            model_provider=m.model_provider,
            model_name=m.model_name,
            created_at=m.created_at.isoformat(),
        )
        for m in conv.messages
    ]

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        messages=messages,
    )


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(session)
    conv = await repo.get_or_create(conversation_id=None, user_id=user_id, title=body.title)
    if body.system_instruction_override:
        conv.system_instruction_override = body.system_instruction_override
        await session.commit()

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        messages=[],
    )
