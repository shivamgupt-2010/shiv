"""
Audit log model for security events, tool executions, and system state transitions.
"""
from typing import Optional
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from database.models.base import Base, TimestampMixin, generate_uuid


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    request_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # auth_failure, rate_limit, fallback, tool_call
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
