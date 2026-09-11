"""
Health and Observability router.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.dependencies import get_db
from database.repositories.provider_repo import ProviderRepository
from monitoring.metrics import MetricsService
from core.identity.prompt_templates import IDENTITY_VERSION

router = APIRouter(prefix="/api/v1", tags=["Observability"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "shivai",
        "version": IDENTITY_VERSION,
    }


@router.get("/health/providers")
async def provider_health(session: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    repo = ProviderRepository(session)
    records = await repo.list_all()
    return {
        "providers": [
            {
                "provider": r.provider,
                "status": r.status,
                "consecutive_failures": r.consecutive_failures,
                "cooldown_until": r.cooldown_until.isoformat() if r.cooldown_until else None,
                "last_error": r.last_error_code,
                "last_success_at": r.last_success_at.isoformat() if r.last_success_at else None,
                "last_failure_at": r.last_failure_at.isoformat() if r.last_failure_at else None,
                "total_requests": r.total_requests,
                "successful_requests": r.successful_requests,
                "failed_requests": r.failed_requests,
            }
            for r in records
        ]
    }


@router.post("/health/providers/reset")
async def reset_provider_health(session: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    repo = ProviderRepository(session)
    await repo.reset_all()
    await session.commit()
    return {"status": "ok", "message": "All provider health records reset to HEALTHY."}


@router.get("/metrics")
async def get_metrics(session: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    return await MetricsService.get_system_metrics(session)
