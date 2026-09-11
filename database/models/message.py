"""
Message model storing individual dialogue turns within a conversation.
Tracks which provider and model fulfilled each assistant message.
"""
from typing import Optional
from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.models.base import Base, TimestampMixin, generate_uuid


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system, tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # AI provider provenance (audit trail)
    model_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Token usage & finish reason
    tokens_input: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    tokens_output: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    finish_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Tool call metadata (if any)
    tool_calls_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
