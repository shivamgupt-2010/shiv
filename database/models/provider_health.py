"""
Provider health tracking table for persistent health status, cooldowns, and quotas.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from database.models.base import Base, TimestampMixin, generate_uuid


class ProviderHealthRecord(Base, TimestampMixin):
    __tablename__ = "provider_health"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    provider: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    
    # Health state: HEALTHY, DEGRADED, RATE_LIMITED, QUOTA_EXHAUSTED, AUTH_FAILED, UNAVAILABLE, UNKNOWN
    status: Mapped[str] = mapped_column(String(30), default="UNKNOWN", index=True, nullable=False)
    
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    last_error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Cumulative stats
    total_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rate_limit_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quota_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
