"""
Unit tests for ShivAI Identity System.
"""
from core.identity.identity_manager import IdentityManager, ShivAIIdentity


def test_identity_defaults():
    identity = ShivAIIdentity()
    assert identity.name == "ShivAI"
    assert identity.version == "1.0.0"
    assert "ShivAI" in identity.name


def test_system_prompt_immutability():
    mgr = IdentityManager()
    prompt = mgr.get_system_prompt(
        agent_instructions="Focus strictly on Python architecture.",
        custom_instructions="User prefers concise answers.",
        user_preferences=["Prefers async Python", "Prefers Pydantic v2"],
    )

    # Asserts ShivAI identity rules are deeply embedded
    assert "You are ShivAI" in prompt
    assert "NEVER claim to be or refer to yourself as ChatGPT" in prompt
    assert "Focus strictly on Python architecture." in prompt
    assert "User prefers concise answers." in prompt
    assert "Prefers async Python" in prompt
    assert "1.0.0" in prompt


def test_identity_does_not_mention_vendor_names():
    mgr = IdentityManager()
    prompt = mgr.get_system_prompt()
    # Ensure it defines boundaries against vendors
    assert "OpenAI" in prompt  # In the prohibition rule
    assert "ShivAI" in prompt
