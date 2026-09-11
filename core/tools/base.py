"""
Secure Tool abstraction base class.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: List[ToolParameter] = Field(default_factory=list)
    required_permission: str = "default"


class Tool(ABC):
    """Abstract base class for all tools accessible to ShivAI agents."""

    def __init__(self, definition: ToolDefinition):
        self.definition = definition

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def description(self) -> str:
        return self.definition.description

    @property
    def required_permission(self) -> str:
        return self.definition.required_permission

    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Executes tool logic safely and returns structured result."""
        pass
