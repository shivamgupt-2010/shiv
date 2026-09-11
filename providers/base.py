"""
Base AI Provider abstraction and unified response schemas.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
from pydantic import BaseModel, Field
from providers.errors import ProviderError, ErrorCategory


class UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ModelIdentifier(BaseModel):
    provider: str
    model: str


class UnifiedResponse(BaseModel):
    request_id: str
    assistant: str = "shivai"
    content: str
    model: ModelIdentifier
    usage: UsageInfo = Field(default_factory=UsageInfo)
    finish_reason: Optional[str] = "stop"
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UnifiedStreamChunk(BaseModel):
    request_id: str
    assistant: str = "shivai"
    delta: str
    finish_reason: Optional[str] = None
    model: Optional[ModelIdentifier] = None


class ProviderCapabilities(BaseModel):
    reasoning: bool = True
    vision: bool = False
    tools: bool = True
    streaming: bool = True
    coding: bool = True


class AIProvider(ABC):
    """Abstract class defining the contract for all external AI model adapters."""

    def __init__(self, provider_name: str, api_key: Optional[str] = None):
        self.provider_name = provider_name
        self.api_key = api_key

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 0)

    @abstractmethod
    async def generate(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> UnifiedResponse:
        """Executes non-streaming completion."""
        pass

    @abstractmethod
    async def stream(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> AsyncIterator[UnifiedStreamChunk]:
        """Executes streaming completion."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Performs a lightweight diagnostic check."""
        pass

    @abstractmethod
    def normalize_error(self, exception: Exception, model: Optional[str] = None) -> ProviderError:
        """Categorizes raw exceptions into a standard ProviderError."""
        pass
