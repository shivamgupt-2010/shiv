"""
Unit tests for Persistent Memory operations.
"""
import pytest
from core.memory.memory_manager import MemoryManager


@pytest.mark.asyncio
async def test_memory_crud_flow(db_session):
    mgr = MemoryManager(db_session)
    user_id = "test-user-id"

    # 1. Add memory
    mem1 = await mgr.remember(
        user_id=user_id,
        key="primary_framework",
        value="FastAPI with Async SQLAlchemy",
        category="preference",
    )
    assert mem1.id is not None

    # 2. Update memory
    mem1_updated = await mgr.remember(
        user_id=user_id,
        key="primary_framework",
        value="FastAPI v2",
        category="preference",
    )
    assert mem1_updated.id == mem1.id
    assert mem1_updated.value == "FastAPI v2"

    # 3. Recall
    recalled = await mgr.recall(user_id=user_id, query="FastAPI")
    assert len(recalled) == 1
    assert recalled[0].key == "primary_framework"

    # 4. Prompt formatting
    formatted = MemoryManager.format_memories_for_prompt(recalled)
    assert "[PREFERENCE] primary_framework: FastAPI v2" in formatted

    # 5. Forget
    success = await mgr.forget(user_id=user_id, memory_id=mem1.id)
    assert success is True

    # 6. Verify gone
    recalled_after = await mgr.recall(user_id=user_id)
    assert len(recalled_after) == 0
