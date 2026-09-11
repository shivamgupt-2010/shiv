"""
ShivAI SDK response data models.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ModelProvenance(BaseModel):
    provider: str
    model: str


class ChatResponse(BaseModel):
    request_id: str
    assistant: str = "shivai"
    content: str
    model: ModelProvenance
    usage: Usage = Field(default_factory=Usage)
    finish_reason: Optional[str] = "stop"
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def conversation_id(self) -> Optional[str]:
        return self.metadata.get("conversation_id")


class StreamChunk(BaseModel):
    request_id: str
    assistant: str = "shivai"
    delta: str
    finish_reason: Optional[str] = None
    model: Optional[ModelProvenance] = None


class MemoryItem(BaseModel):
    id: str
    key: str
    value: str
    category: str
    importance: float
    confidence: float
    source: str
    created_at: str


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    created_at: str


class ConversationItem(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: Optional[List[MessageItem]] = None
