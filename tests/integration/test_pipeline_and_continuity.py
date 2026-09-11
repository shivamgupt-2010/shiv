"""
Integration tests for End-to-End Chat, Streaming, Identity Continuity, and DB Persistence.
"""
import pytest
import respx
import httpx
from providers.registry import provider_registry
from database.session import async_session_factory
from database.repositories.conversation_repo import ConversationRepository
from database.repositories.memory_repo import MemoryRepository


@pytest.mark.asyncio
@respx.mock
async def test_api_chat_endpoint(async_client):
    provider_registry.get_provider("openai", api_key="test-key")

    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "I am ShivAI, ready to assist."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
            },
        )
    )

    response = await async_client.post(
        "/api/v1/chat",
        json={"message": "Who are you?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["assistant"] == "shivai"
    assert data["content"] == "I am ShivAI, ready to assist."
    assert "conversation_id" in data["metadata"]


@pytest.mark.asyncio
@respx.mock
async def test_api_streaming_endpoint(async_client):
    provider_registry.get_provider("openai", api_key="test-key")

    sse_lines = [
        'data: {"choices": [{"delta": {"content": "Shiv"}, "finish_reason": null}]}\n\n',
        'data: {"choices": [{"delta": {"content": "AI is live."}, "finish_reason": "stop"}]}\n\n',
        'data: [DONE]\n\n',
    ]

    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            text="".join(sse_lines),
            headers={"content-type": "text/event-stream"},
        )
    )

    response = await async_client.post(
        "/api/v1/chat/stream",
        json={"message": "Stream a response."},
    )

    assert response.status_code == 200
    body = response.text
    assert "Shiv" in body
    assert "AI is live." in body
    assert "[DONE]" in body


@pytest.mark.asyncio
@respx.mock
async def test_identity_and_conversation_continuity_across_model_switches(db_session):
    """
    Test 6 & 7: Consecutive messages handled by different models.
    Turn 1 -> Model A (OpenAI)
    Turn 2 -> Model B (Groq)
    Verify:
    - Same conversation ID
    - Both messages stored in history
    - ShivAI identity remains consistent
    """
    from core.orchestration.orchestrator import ShivAIOrchestrator

    provider_registry.get_provider("openai", api_key="test-key-1")
    provider_registry.get_provider("groq", api_key="test-key-2")

    # Turn 1 mock (OpenAI)
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ShivAI Turn 1: I remember you are an engineer."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            },
        )
    )

    orchestrator = ShivAIOrchestrator(db_session)
    res1 = await orchestrator.process_chat(
        user_message="Hello, I am an engineer.",
        user_id="user-continuity",
        preferred_provider="openai",
    )
    conv_id = res1.metadata["conversation_id"]
    assert res1.model.provider == "openai"
    assert res1.assistant == "shivai"

    # Turn 2: Simulate OpenAI quota exhausted, forcing fallback to Groq
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            429,
            json={"error": {"message": "You exceeded your current quota"}},
        )
    )
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ShivAI Turn 2: Continuing our technical project seamlessly."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 25, "completion_tokens": 10, "total_tokens": 35},
            },
        )
    )

    res2 = await orchestrator.process_chat(
        user_message="What should we build next?",
        user_id="user-continuity",
        conversation_id=conv_id,
        preferred_provider="openai",  # Will fail over to groq
    )

    # Asserts
    assert res2.assistant == "shivai"
    assert res2.model.provider == "groq"
    assert res2.metadata["conversation_id"] == conv_id

    # Verify conversation history has both turns
    conv_repo = ConversationRepository(db_session)
    history = await conv_repo.get_recent_messages(conversation_id=conv_id, limit=10)
    assert len(history) == 4  # (User1, Assistant1, User2, Assistant2)
    roles = [m.role for m in history]
    assert roles == ["user", "assistant", "user", "assistant"]


@pytest.mark.asyncio
async def test_database_persistence_across_sessions():
    """
    Test 12: Restarting backend session does not destroy conversations or memory.
    """
    user_id = "persistent-user"

    # Session 1: write
    async with async_session_factory() as session1:
        mem_repo = MemoryRepository(session1)
        conv_repo = ConversationRepository(session1)

        await mem_repo.add_or_update_memory(
            user_id=user_id,
            key="favorite_language",
            value="Rust",
            category="preference",
        )

        conv = await conv_repo.get_or_create(conversation_id=None, user_id=user_id, title="Persistent Thread")
        await conv_repo.add_message(
            conversation_id=conv.id,
            role="user",
            content="Save this state.",
        )
        await session1.commit()
        saved_conv_id = conv.id

    # Session 2: read from completely new session (simulating backend reboot)
    async with async_session_factory() as session2:
        mem_repo2 = MemoryRepository(session2)
        conv_repo2 = ConversationRepository(session2)

        memories = await mem_repo2.get_active_memories(user_id=user_id)
        assert len(memories) == 1
        assert memories[0].key == "favorite_language"
        assert memories[0].value == "Rust"

        conv_loaded = await conv_repo2.get_by_id(saved_conv_id)
        assert conv_loaded is not None
        assert conv_loaded.title == "Persistent Thread"
        assert len(conv_loaded.messages) == 1
        assert conv_loaded.messages[0].content == "Save this state."
