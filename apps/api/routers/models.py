"""
Models inspection router.
"""
from typing import List, Dict, Any
from fastapi import APIRouter
from core.routing.router import model_router
from providers.registry import provider_registry

router = APIRouter(prefix="/api/v1/models", tags=["Models"])


@router.get("", response_model=List[Dict[str, Any]])
async def list_models():
    """
    Returns the declarative catalog of models available to ShivAI's Model Router.
    """
    configured_providers = set(provider_registry.list_configured())
    models = model_router.list_all_models()

    return [
        {
            "id": m.id,
            "provider": m.provider,
            "model": m.model,
            "priority": m.priority,
            "capabilities": m.capabilities.model_dump(),
            "context_limit": m.context_limit,
            "max_output_tokens": m.max_output_tokens,
            "cost_tier": m.cost_tier,
            "status": m.status,
            "provider_configured": m.provider in configured_providers,
        }
        for m in models
    ]
