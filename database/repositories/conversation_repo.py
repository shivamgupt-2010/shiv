"""
Repository for Conversation and Message persistence.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from database.models.conversation import Conversation
from database.models.message import Message


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, conversation_id: Optional[str], user_id: str, title: Optional[str] = None) -> Conversation:
        if conversation_id:
            stmt = select(Conversation).where(Conversation.id == conversation_id).options(selectinload(Conversation.messages))
            res = await self.session.execute(stmt)
            conv = res.scalar_one_or_none()
            if conv:
                return conv
        
        # Ensure user exists for foreign key integrity
        from database.models.user import User
        user_stmt = select(User).where(User.id == user_id)
        user_res = await self.session.execute(user_stmt)
        if not user_res.scalar_one_or_none():
            safe_username = f"user_{user_id[:8]}" if len(user_id) >= 8 else f"user_{user_id}"
            new_u = User(id=user_id, username=safe_username)
            self.session.add(new_u)
            await self.session.flush()

        # Create new
        new_conv = Conversation(
            user_id=user_id,
            title=title or "New Conversation",
        )
        self.session.add(new_conv)
        await self.session.flush()
        return new_conv

    async def get_by_id(self, conversation_id: str) -> Optional[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_user_conversations(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        tokens_input: Optional[int] = 0,
        tokens_output: Optional[int] = 0,
        finish_reason: Optional[str] = None,
        tool_calls_json: Optional[str] = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model_provider=model_provider,
            model_name=model_name,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            finish_reason=finish_reason,
            tool_calls_json=tool_calls_json,
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def get_recent_messages(self, conversation_id: str, limit: int = 20) -> List[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        res = await self.session.execute(stmt)
        all_msgs = list(res.scalars().all())
        if limit and len(all_msgs) > limit:
            return all_msgs[-limit:]
        return all_msgs
