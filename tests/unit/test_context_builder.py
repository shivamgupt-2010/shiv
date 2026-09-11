"""
Unit tests for Context Builder and Token Estimation.
"""
from core.context.context_builder import ContextBuilder
from core.context.token_counter import estimate_tokens
from database.models.message import Message
from database.models.memory import Memory


def test_token_estimation():
    assert estimate_tokens("hello world") >= 2
    assert estimate_tokens("") == 0


def test_context_builder_assembly():
    builder = ContextBuilder(default_max_context_tokens=1000)

    memories = [
        Memory(user_id="u1", key="language_preference", value="Python 3.11", category="preference")
    ]
    history = [
        Message(conversation_id="c1", role="user", content="Turn 1: What is FastAPI?"),
        Message(conversation_id="c1", role="assistant", content="Turn 1: FastAPI is an async web framework."),
    ]

    messages = builder.build_context(
        user_message="Tell me more about Pydantic.",
        conversation_history=history,
        memories=memories,
    )

    assert len(messages) == 4
    assert messages[0]["role"] == "system"
    assert "Python 3.11" in messages[0]["content"]
    assert "ShivAI" in messages[0]["content"]
    assert messages[1]["content"] == "Turn 1: What is FastAPI?"
    assert messages[3]["content"] == "Tell me more about Pydantic."


def test_context_builder_budget_pruning():
    # Strict budget that forces older messages to be pruned
    builder = ContextBuilder(default_max_context_tokens=200, reserved_output_tokens=50)

    history = [
        Message(conversation_id="c1", role="user", content="A" * 300),  # Long message
        Message(conversation_id="c1", role="assistant", content="Short reply"),
    ]

    messages = builder.build_context(
        user_message="Current short question",
        conversation_history=history,
    )

    # Long message should be pruned to fit budget, but system prompt and current question remain
    contents = [m["content"] for m in messages]
    assert not any("A" * 300 in c for c in contents)
    assert messages[-1]["content"] == "Current short question"
