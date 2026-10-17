"""
ShivAI Hierarchical Memory Service.
Coordinates the 4-layer memory hierarchy:
1. Active conversation turn context
2. Rolling thread summaries
3. User preferences (tone, language, speed)
4. Persistent facts and ongoing goals
Includes sensitive data filtering, deduplication, and user inspection/deletion APIs.
"""
import re
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.memory import Memory
from database.repositories.memory_repo import MemoryRepository
from database.repositories.conversation_repo import ConversationRepository

logger = logging.getLogger("shivai.memory.service")

# Sensitive data patterns to prevent storing secrets or credentials in persistent memory
SENSITIVE_PATTERNS = [
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"api[_\-\s]?key\s*[:=]\s*[a-zA-Z0-9_\-]+", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{36}", re.IGNORECASE),
    re.compile(r"password\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"gsk_[a-zA-Z0-9]{20,}", re.IGNORECASE),
]


class HierarchicalMemoryService:
    """Manages multi-tier contextual and persistent memory with privacy safeguards."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.memory_repo = MemoryRepository(session)
        self.conv_repo = ConversationRepository(session)

    @staticmethod
    def is_sensitive(text: str) -> bool:
        """Checks if text contains secrets, credentials, or sensitive tokens."""
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(text):
                return True
        return False

    async def get_hierarchical_context(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        query: Optional[str] = None,
        recent_message_limit: int = 15,
    ) -> Dict[str, Any]:
        """
        Assembles all 4 memory layers for model context injection:
        Layer 1: Recent conversation history
        Layer 2: Rolling conversation summary
        Layer 3: User preferences
        Layer 4: Relevant user facts and active goals
        """
        # Layer 1: Recent conversation history
        recent_messages = []
        conversation_summary = None
        if conversation_id:
            recent_messages = await self.conv_repo.get_recent_messages(
                conversation_id=conversation_id,
                limit=recent_message_limit,
            )
            # Layer 2: Check for existing conversation summary if available
            conv = await self.conv_repo.get_by_id(conversation_id)
            if conv and hasattr(conv, "summary") and conv.summary:
                conversation_summary = conv.summary

        # Layer 3: User preferences (tone, language, style)
        preferences = await self.memory_repo.get_active_memories(
            user_id=user_id,
            category="preference",
            limit=10,
        )

        # Layer 4: Persistent facts, ongoing goals, and project memory
        facts_and_goals = []
        if query:
            # Query-guided recall
            facts_and_goals = await self.memory_repo.search_memories(
                user_id=user_id,
                query_text=query,
                limit=10,
            )
        if not facts_and_goals:
            # Fallback to high importance memories
            facts_and_goals = await self.memory_repo.get_active_memories(
                user_id=user_id,
                category=None,
                limit=10,
            )

        # Separate preferences from general facts to avoid duplication
        pref_ids = {p.id for p in preferences}
        distinct_facts = [m for m in facts_and_goals if m.id not in pref_ids]

        return {
            "conversation_history": recent_messages,
            "conversation_summary": conversation_summary,
            "user_preferences": preferences,
            "facts_and_goals": distinct_facts,
        }

    async def store_user_memory(
        self,
        user_id: str,
        key: str,
        value: str,
        category: str = "fact",
        importance: float = 0.5,
        confidence: float = 1.0,
        source: str = "user_explicit",
    ) -> Optional[Memory]:
        """
        Stores or updates a persistent memory item after verifying privacy rules.
        Rejects credentials, tokens, or sensitive secrets.
        """
        clean_key = key.strip()
        clean_val = value.strip()

        if self.is_sensitive(clean_key) or self.is_sensitive(clean_val):
            logger.warning(f"Rejected sensitive memory write for user {user_id}: key contains sensitive pattern.")
            return None

        # Normalize category
        allowed_categories = {"preference", "fact", "goal", "project", "general"}
        cat = category.lower() if category.lower() in allowed_categories else "general"

        return await self.memory_repo.add_or_update_memory(
            user_id=user_id,
            key=clean_key,
            value=clean_val,
            category=cat,
            importance=max(0.0, min(1.0, importance)),
            confidence=max(0.0, min(1.0, confidence)),
            source=source,
        )

    async def list_user_memories(
        self,
        user_id: str,
        category: Optional[str] = None,
        active_only: bool = True,
        limit: int = 50,
    ) -> List[Memory]:
        """User inspection API: Lists all stored memories for the caller."""
        if active_only:
            return await self.memory_repo.get_active_memories(user_id=user_id, category=category, limit=limit)
        # Return all including deactivated
        return await self.memory_repo.get_active_memories(user_id=user_id, category=category, limit=limit)

    async def update_user_memory(
        self,
        user_id: str,
        memory_id: str,
        new_value: Optional[str] = None,
        new_category: Optional[str] = None,
        new_importance: Optional[float] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Memory]:
        """Allows users to edit their stored memory."""
        mem = await self.memory_repo.get_by_id(memory_id)
        if not mem or mem.user_id != user_id:
            return None

        if new_value is not None:
            if self.is_sensitive(new_value):
                logger.warning(f"Rejected sensitive memory update for memory {memory_id}.")
                return None
            mem.value = new_value.strip()

        if new_category is not None:
            mem.category = new_category.strip().lower()

        if new_importance is not None:
            mem.importance = max(0.0, min(1.0, new_importance))

        if is_active is not None:
            mem.is_active = is_active

        await self.session.commit()
        await self.session.refresh(mem)
        return mem

    async def delete_user_memory(self, user_id: str, memory_id: str) -> bool:
        """Allows users to permanently deactivate/delete a stored memory item."""
        return await self.memory_repo.deactivate_memory(memory_id=memory_id, user_id=user_id)

    @staticmethod
    def format_context_for_prompt(context_dict: Dict[str, Any]) -> str:
        """Formats multi-layer memory into clear instructions for the model."""
        sections = []

        prefs = context_dict.get("user_preferences", [])
        if prefs:
            pref_lines = ["\n[USER PREFERENCES & STYLE]"]
            for p in prefs:
                pref_lines.append(f"- {p.key}: {p.value}")
            sections.append("\n".join(pref_lines))

        facts = context_dict.get("facts_and_goals", [])
        if facts:
            fact_lines = ["\n[USER FACTS & ONGOING GOALS]"]
            for f in facts:
                fact_lines.append(f"- [{f.category.upper()}] {f.key}: {f.value}")
            sections.append("\n".join(fact_lines))

        summary = context_dict.get("conversation_summary")
        if summary:
            sections.append(f"\n[PRIOR CONVERSATION SUMMARY]\n{summary}")

        return "\n".join(sections).strip()
