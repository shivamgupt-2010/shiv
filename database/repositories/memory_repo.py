"""
Repository for Persistent Memory management.
"""
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from database.models.memory import Memory


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_or_update_memory(
        self,
        user_id: str,
        key: str,
        value: str,
        category: str = "general",
        importance: float = 0.5,
        confidence: float = 1.0,
        source: str = "user_explicit",
        expires_at: Optional[datetime] = None,
    ) -> Memory:
        # Check if active memory with same user_id and key exists
        stmt = select(Memory).where(
            and_(
                Memory.user_id == user_id,
                Memory.key == key,
                Memory.is_active == True,
            )
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.value = value
            existing.category = category
            existing.importance = importance
            existing.confidence = confidence
            existing.source = source
            existing.expires_at = expires_at
            await self.session.flush()
            return existing

        # Ensure user exists for foreign key integrity
        from database.models.user import User
        user_stmt = select(User).where(User.id == user_id)
        user_res = await self.session.execute(user_stmt)
        if not user_res.scalar_one_or_none():
            safe_username = f"user_{user_id[:8]}" if len(user_id) >= 8 else f"user_{user_id}"
            new_u = User(id=user_id, username=safe_username)
            self.session.add(new_u)
            await self.session.flush()

        new_mem = Memory(
            user_id=user_id,
            key=key,
            value=value,
            category=category,
            importance=importance,
            confidence=confidence,
            source=source,
            expires_at=expires_at,
            is_active=True,
        )
        self.session.add(new_mem)
        await self.session.flush()
        return new_mem

    async def get_active_memories(
        self, user_id: str, category: Optional[str] = None, limit: int = 50
    ) -> List[Memory]:
        now = datetime.now(timezone.utc)
        conditions = [
            Memory.user_id == user_id,
            Memory.is_active == True,
            or_(Memory.expires_at == None, Memory.expires_at > now),
        ]
        if category:
            conditions.append(Memory.category == category)

        stmt = (
            select(Memory)
            .where(and_(*conditions))
            .order_by(desc(Memory.importance), desc(Memory.created_at))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def search_memories(self, user_id: str, query_text: str, limit: int = 10) -> List[Memory]:
        """Simple substring matching search across key and value (extensible to vector search)."""
        now = datetime.now(timezone.utc)
        pattern = f"%{query_text}%"
        stmt = (
            select(Memory)
            .where(
                and_(
                    Memory.user_id == user_id,
                    Memory.is_active == True,
                    or_(Memory.expires_at == None, Memory.expires_at > now),
                    or_(Memory.key.ilike(pattern), Memory.value.ilike(pattern)),
                )
            )
            .order_by(desc(Memory.importance))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def deactivate_memory(self, memory_id: str, user_id: str) -> bool:
        stmt = select(Memory).where(and_(Memory.id == memory_id, Memory.user_id == user_id))
        res = await self.session.execute(stmt)
        mem = res.scalar_one_or_none()
        if mem:
            mem.is_active = False
            await self.session.flush()
            return True
        return False
