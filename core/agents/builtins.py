"""
Built-in specialized ShivAI agents.
"""
from core.agents.base import BaseAgent, AgentDefinition


class GeneralAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            AgentDefinition(
                name="General Agent",
                purpose="Handles conversational dialog, multi-domain queries, and general problem solving.",
                instructions="Provide balanced, insightful, articulate, and direct answers.",
                required_capabilities={"reasoning": True},
                allowed_tools=["calculator", "get_current_time"],
                permissions=["default", "calculator", "datetime"],
            )
        )


class CodingAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            AgentDefinition(
                name="Coding Agent",
                purpose="Writes, reviews, refactors, and debugs robust production-grade code.",
                instructions=(
                    "Focus on software engineering best practices, strict typing, clean architecture, "
                    "thorough error handling, and performance optimization. Output complete, working code blocks."
                ),
                required_capabilities={"coding": True, "reasoning": True},
                allowed_tools=["calculator", "get_current_time"],
                permissions=["default", "calculator", "datetime"],
            )
        )


class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            AgentDefinition(
                name="Research Agent",
                purpose="Conducts deep investigations, synthesizes facts, and extracts technical citations.",
                instructions="Synthesize comprehensive evidence, evaluate nuances, and provide structured analyses.",
                required_capabilities={"reasoning": True},
                allowed_tools=["web_search", "get_current_time"],
                permissions=["default", "web_search", "datetime"],
            )
        )


class PlanningAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            AgentDefinition(
                name="Planning Agent",
                purpose="Creates multi-step project roadmaps, architectures, and execution milestones.",
                instructions="Break complex objectives down into logical, prioritized, verifiable execution phases.",
                required_capabilities={"reasoning": True},
                allowed_tools=["get_current_time"],
                permissions=["default", "datetime"],
            )
        )


class MathAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            AgentDefinition(
                name="Math Agent",
                purpose="Performs exact mathematical proofs, calculations, statistics, and numeric verifications.",
                instructions="Verify all calculations step by step with mathematical rigor. Utilize the calculator tool for verification.",
                required_capabilities={"reasoning": True},
                allowed_tools=["calculator"],
                permissions=["default", "calculator"],
            )
        )


class VisionAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            AgentDefinition(
                name="Vision Agent",
                purpose="Analyzes visual inputs, diagrams, screenshots, and visual user interfaces.",
                instructions="Inspect visual details carefully, extract text, and explain layout and structure.",
                required_capabilities={"vision": True},
                allowed_tools=[],
                permissions=["default"],
            )
        )


class SystemAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            AgentDefinition(
                name="System Agent",
                purpose="Manages system health, logs, database state, and configuration metrics.",
                instructions="Inspect and report internal system health, usage records, and diagnostic signals.",
                required_capabilities={"reasoning": True},
                allowed_tools=["get_current_time"],
                permissions=["default", "datetime", "admin"],
            )
        )
