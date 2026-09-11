"""
Memory Manager Subsystem.
Orchestrates short-term conversation context, long-term persistent user facts,
and task-specific contextual retrieval.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.memory import Memory
from database.repositories.memory_repo import MemoryRepository


class MemoryManager:
    """High-level interface for managing long-term and contextual memories."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MemoryRepository(session)

    async def remember(
        self,
        user_id: str,
        key: str,
        value: str,
        category: str = "general",
        importance: float = 0.5,
        confidence: float = 1.0,
        source: str = "user_explicit",
    ) -> Memory:
        """Stores or updates a persistent memory item."""
        return await self.repo.add_or_update_memory(
            user_id=user_id,
            key=key,
            value=value,
            category=category,
            importance=importance,
            confidence=confidence,
            source=source,
        )

    async def recall(
        self,
        user_id: str,
        query: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 15,
    ) -> List[Memory]:
        """Recalls active memories relevant to the query or category."""
        if query:
            # Substring / keyword search (extensible to vector search)
            memories = await self.repo.search_memories(user_id=user_id, query_text=query, limit=limit)
            if memories:
                return memories

        # Fallback to highest importance active memories
        return await self.repo.get_active_memories(user_id=user_id, category=category, limit=limit)

    async def forget(self, user_id: str, memory_id: str) -> bool:
        """Soft-deletes/deactivates a memory item."""
        return await self.repo.deactivate_memory(memory_id=memory_id, user_id=user_id)

    @staticmethod
    def format_memories_for_prompt(memories: List[Memory]) -> str:
        """Formats recalled memories into a concise prompt block."""
        if not memories:
            return ""

        lines = ["[PERSISTENT MEMORY / USER FACTS]"]
        for m in memories:
            lines.append(f"- [{m.category.upper()}] {m.key}: {m.value}")
        return "\n".join(lines)
