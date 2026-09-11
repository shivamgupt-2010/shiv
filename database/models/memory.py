"""
Persistent Memory model storing semantic facts, preferences, and long-term user context.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from database.models.base import Base, TimestampMixin, generate_uuid


class Memory(Base, TimestampMixin):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    
    # Memory identity & category
    key: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="general", index=True, nullable=False)  # preference, fact, user_profile, system
    
    # Metadata
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)  # 0.0 - 1.0
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)  # 0.0 - 1.0
    source: Mapped[str] = mapped_column(String(50), default="user_explicit", nullable=False)  # user_explicit, inferred, system
    
    # Expiration & soft deletion
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    
    # Reserved slot for future vector embeddings (JSON array of floats or vector type)
    embedding_meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
