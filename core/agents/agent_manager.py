"""
Agent Manager.
Maintains available agents and provides task-to-agent mapping.
"""
from typing import Dict, List, Optional, Any
from core.agents.base import BaseAgent
from core.agents.builtins import (
    GeneralAgent,
    CodingAgent,
    ResearchAgent,
    PlanningAgent,
    MathAgent,
    VisionAgent,
    SystemAgent,
)


class AgentManager:
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register("general", GeneralAgent())
        self.register("chat", GeneralAgent())
        self.register("coding", CodingAgent())
        self.register("research", ResearchAgent())
        self.register("planning", PlanningAgent())
        self.register("math", MathAgent())
        self.register("vision", VisionAgent())
        self.register("system", SystemAgent())
        self.register("study", ResearchAgent())

    def register(self, key: str, agent: BaseAgent) -> None:
        self._agents[key.lower()] = agent

    def get_agent(self, key: str) -> BaseAgent:
        return self._agents.get(key.lower(), self._agents["general"])

    def list_agents(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": k,
                "name": a.name,
                "purpose": a.purpose,
                "required_capabilities": a.required_capabilities,
                "allowed_tools": a.allowed_tools,
            }
            for k, a in self._agents.items()
        ]


agent_manager = AgentManager()
