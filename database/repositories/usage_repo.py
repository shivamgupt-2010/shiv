"""
Repository for recording usage tokens and request performance metrics.
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from database.models.usage import UsageRecord


class UsageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_usage(
        self,
        request_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        status: str = "success",
        user_id: str = None,
        conversation_id: str = None,
        error_category: str = None,
        estimated_cost: float = 0.0,
    ) -> UsageRecord:
        record = UsageRecord(
            request_id=request_id,
            user_id=user_id,
            conversation_id=conversation_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms,
            status=status,
            error_category=error_category,
            estimated_cost=estimated_cost,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Calculates global tokens, request counts, and average latencies."""
        stmt = select(
            func.count(UsageRecord.id).label("total_requests"),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(UsageRecord.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.avg(UsageRecord.latency_ms), 0.0).label("avg_latency_ms"),
        )
        res = await self.session.execute(stmt)
        row = res.one()
        return {
            "total_requests": row.total_requests,
            "total_input_tokens": row.total_input_tokens,
            "total_output_tokens": row.total_output_tokens,
            "total_tokens": row.total_tokens,
            "avg_latency_ms": round(float(row.avg_latency_ms), 2),
        }
