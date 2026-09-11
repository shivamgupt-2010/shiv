"""
Base Agent abstraction.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class AgentDefinition(BaseModel):
    name: str
    purpose: str
    instructions: str
    required_capabilities: Dict[str, bool] = Field(default_factory=dict)
    allowed_tools: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    preferred_provider: Optional[str] = None


class BaseAgent:
    def __init__(self, definition: AgentDefinition):
        self.definition = definition

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def purpose(self) -> str:
        return self.definition.purpose

    @property
    def instructions(self) -> str:
        return self.definition.instructions

    @property
    def required_capabilities(self) -> Dict[str, bool]:
        return self.definition.required_capabilities

    @property
    def allowed_tools(self) -> List[str]:
        return self.definition.allowed_tools

    @property
    def permissions(self) -> List[str]:
        return self.definition.permissions
