"""
ShivAI V2 Model Catalog Endpoint.
Exposes GET /v2/models and GET /api/v2/models.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, status
from core.routing.registry import model_registry

router = APIRouter(tags=["V2 Model Catalog"])


@router.get(
    "/v2/models",
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/api/v2/models",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def list_v2_models() -> Dict[str, Any]:
    """
    Returns all models available in the central model registry,
    along with their capability flags, context limits, and score profiles.
    """
    models = model_registry.list_all(enabled_only=True)
    return {
        "count": len(models),
        "models": [
            {
                "id": m.model_id,
                "provider": m.provider,
                "model": m.model_name,
                "display_name": m.display_name,
                "context_window": m.context_window,
                "max_output_tokens": m.max_output_tokens,
                "cost_tier": m.cost_tier,
                "capabilities": m.capabilities.model_dump(),
                "supports_streaming": m.supports_streaming,
                "supports_structured_output": m.supports_structured_output,
                "scores": {
                    "speed": m.speed_score,
                    "quality": m.quality_score,
                    "cost": m.cost_score,
                    "priority": m.priority,
                },
            }
            for m in models
        ],
    }
