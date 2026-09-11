"""
System and Provider Metrics Subsystem.
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.usage_repo import UsageRepository
from database.repositories.provider_repo import ProviderRepository
from providers.registry import provider_registry


class MetricsService:
    @staticmethod
    async def get_system_metrics(session: AsyncSession) -> Dict[str, Any]:
        usage_repo = UsageRepository(session)
        provider_repo = ProviderRepository(session)

        stats = await usage_repo.get_metrics_summary()
        providers_health = await provider_repo.list_all()

        health_summary = {}
        for p in providers_health:
            health_summary[p.provider] = {
                "status": p.status,
                "total_requests": p.total_requests,
                "successful_requests": p.successful_requests,
                "failed_requests": p.failed_requests,
                "rate_limit_events": p.rate_limit_events,
                "quota_events": p.quota_events,
                "last_error": p.last_error_code,
            }

        return {
            "status": "operational",
            "usage": stats,
            "configured_providers": provider_registry.list_configured(),
            "registered_providers": provider_registry.list_registered(),
            "providers_health": health_summary,
        }
