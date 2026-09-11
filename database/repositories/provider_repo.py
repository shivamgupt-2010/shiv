"""
Repository for Provider Health and Availability state tracking.
"""
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.provider_health import ProviderHealthRecord


class ProviderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, provider: str) -> ProviderHealthRecord:
        stmt = select(ProviderHealthRecord).where(ProviderHealthRecord.provider == provider)
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            record = ProviderHealthRecord(
                provider=provider,
                status="HEALTHY",
                consecutive_failures=0,
            )
            self.session.add(record)
            await self.session.flush()
        return record

    async def record_success(self, provider: str) -> ProviderHealthRecord:
        record = await self.get_or_create(provider)
        now = datetime.now(timezone.utc)
        record.status = "HEALTHY"
        record.consecutive_failures = 0
        record.last_success_at = now
        record.cooldown_until = None
        record.total_requests += 1
        record.successful_requests += 1
        await self.session.flush()
        return record

    async def record_failure(
        self,
        provider: str,
        error_category: str,
        error_message: str,
        cooldown_seconds: int = 60,
    ) -> ProviderHealthRecord:
        record = await self.get_or_create(provider)
        now = datetime.now(timezone.utc)
        record.consecutive_failures += 1
        record.last_failure_at = now
        record.last_error_code = error_category
        record.last_error_message = error_message[:500] if error_message else None
        record.total_requests += 1
        record.failed_requests += 1

        if error_category in ("QUOTA_EXCEEDED", "INSUFFICIENT_CREDITS"):
            record.status = "QUOTA_EXHAUSTED"
            record.quota_events += 1
            # Quotas usually reset on hourly/daily cycles; set cooldown to minimum 10 minutes
            record.cooldown_until = now + timedelta(seconds=max(cooldown_seconds, 600))
        elif error_category == "RATE_LIMIT":
            record.status = "RATE_LIMITED"
            record.rate_limit_events += 1
            # Temporary rate limit cooldown (e.g. 30s - 120s)
            record.cooldown_until = now + timedelta(seconds=cooldown_seconds)
        elif error_category == "AUTH_ERROR":
            record.status = "AUTH_FAILED"
            # Auth failures indicate invalid key; cooldown long to avoid hammer
            record.cooldown_until = now + timedelta(seconds=3600)
        else:
            record.status = "DEGRADED"
            record.cooldown_until = now + timedelta(seconds=cooldown_seconds)

        await self.session.flush()
        return record

    async def list_all(self) -> List[ProviderHealthRecord]:
        stmt = select(ProviderHealthRecord).order_by(ProviderHealthRecord.provider)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def is_provider_available(self, provider: str) -> bool:
        record = await self.get_or_create(provider)
        now = datetime.now(timezone.utc)

        # If in cooldown, not available
        if record.cooldown_until and record.cooldown_until > now:
            return False

        # If cooldown expired, allow probe
        if record.cooldown_until and record.cooldown_until <= now:
            if record.status in ("RATE_LIMITED", "DEGRADED"):
                record.status = "HEALTHY"
                record.cooldown_until = None
                await self.session.flush()
                return True

        if record.status == "AUTH_FAILED":
            return False

        return True
