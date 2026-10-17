"""
ShivAI V2 Health & Observability Endpoints.
Exposes GET /v2/health and GET /v2/providers/health.
"""
from typing import Dict, Any
from fastapi import APIRouter, status
from core.resilience.circuit_breaker import circuit_breaker_registry
from core.resilience.key_pool import key_pool_manager
from providers.registry import provider_registry

router = APIRouter(tags=["V2 Health & Observability"])


@router.get(
    "/v2/health",
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/api/v2/health",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def v2_health_check() -> Dict[str, Any]:
    """Lightweight top-level health probe."""
    configured_providers = provider_registry.list_configured()
    circuit_statuses = circuit_breaker_registry.get_all_statuses()

    # Determine overall status
    has_healthy_provider = len(configured_providers) > 0
    all_open = (
        len(circuit_statuses) > 0
        and all(cb["state"] == "OPEN" for cb in circuit_statuses.values())
    )

    if not has_healthy_provider or all_open:
        overall_status = "DEGRADED"
    else:
        overall_status = "HEALTHY"

    return {
        "status": overall_status,
        "version": "2.0.0",
        "configured_providers": configured_providers,
        "circuit_breakers_active": len(circuit_statuses),
    }


@router.get(
    "/v2/providers/health",
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/api/v2/providers/health",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def v2_providers_health() -> Dict[str, Any]:
    """
    Detailed telemetry on provider availability, circuit breaker states,
    and key pool health without exposing raw API keys.
    """
    circuit_statuses = circuit_breaker_registry.get_all_statuses()
    key_pool_statuses = key_pool_manager.get_all_statuses()

    provider_details = {}
    for prov_name in provider_registry.list_configured():
        breaker_info = circuit_statuses.get(prov_name, {"state": "CLOSED", "failure_count": 0})
        key_pool_info = key_pool_statuses.get(prov_name, [])

        provider_details[prov_name] = {
            "status": "HEALTHY" if breaker_info["state"] == "CLOSED" else breaker_info["state"],
            "circuit_breaker": breaker_info,
            "key_pool": [
                {
                    "key_id": k["key_id"],
                    "enabled": k["enabled"],
                    "healthy": k["healthy"],
                    "rate_limited": k["rate_limited_until"] > 0,
                    "failure_count": k["failure_count"],
                }
                for k in key_pool_info
            ],
        }

    return {
        "providers": provider_details,
    }
