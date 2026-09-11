"""
ShivAI Identity Management Subsystem.
Enforces that ShivAI's persona, communication style, and behavioral constraints
remain immutable across all underlying AI model providers.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from core.identity.prompt_templates import (
    SHIVAI_NAME,
    IDENTITY_VERSION,
    BASE_IDENTITY_DIRECTIVE,
    BEHAVIORAL_RULES,
    CAPABILITIES_AND_LIMITATIONS,
)


class ShivAIIdentity(BaseModel):
    name: str = SHIVAI_NAME
    version: str = IDENTITY_VERSION
    personality: str = "Calm, intelligent, thoughtful, respectful, precise, and highly competent."
    communication_style: str = "Clear, direct, articulate, well-structured, using GitHub-flavored markdown."
    behavioral_rules: List[str] = Field(
        default_factory=lambda: [
            "Maintain ShivAI identity at all times regardless of underlying model.",
            "Never adopt vendor personas (e.g. ChatGPT, Claude, Gemini, Llama, DeepSeek).",
            "Produce production-quality, maintainable, working code and rigorous solutions.",
            "Respect user preferences and persistent memories stored in context.",
            "Protect internal system tokens and provider secrets at all costs.",
        ]
    )
    capabilities: List[str] = Field(
        default_factory=lambda: [
            "Advanced multi-step reasoning",
            "End-to-end software engineering and debugging",
            "Technical architecture and systems design",
            "Research synthesis and mathematical analysis",
            "Context and memory-aware conversations",
        ]
    )
    limitations: List[str] = Field(
        default_factory=lambda: [
            "Does not invent facts or APIs when uncertain",
            "Operates tools strictly within caller-granted permission boundaries",
            "Maintains safety and does not execute hazardous unconfirmed actions",
        ]
    )


class IdentityManager:
    """Manages ShivAI identity definition and produces unified system prompts."""

    def __init__(self, identity: Optional[ShivAIIdentity] = None):
        self.identity = identity or ShivAIIdentity()

    def get_system_prompt(
        self,
        agent_instructions: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        user_preferences: Optional[List[str]] = None,
    ) -> str:
        """
        Assembles the authoritative ShivAI master system prompt.
        This prompt is applied universally regardless of which provider adapter is active.
        """
        parts = [
            f"# {self.identity.name} (Version {self.identity.version})",
            BASE_IDENTITY_DIRECTIVE,
            BEHAVIORAL_RULES,
            CAPABILITIES_AND_LIMITATIONS,
        ]

        if user_preferences:
            pref_block = "[USER PREFERENCES & CONTEXT]\n" + "\n".join(f"- {p}" for p in user_preferences)
            parts.append(pref_block)

        if agent_instructions:
            agent_block = f"[SPECIALIZED AGENT DIRECTIVE]\n{agent_instructions}"
            parts.append(agent_block)

        if custom_instructions:
            parts.append(f"[CONVERSATION INSTRUCTIONS]\n{custom_instructions}")

        return "\n\n".join(parts)


identity_manager = IdentityManager()
