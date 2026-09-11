"""
Unit tests for Model Router and candidate ranking.
"""
import pytest
from core.routing.router import ModelRouter, ModelConfig, ModelCapabilities
from providers.registry import provider_registry


@pytest.mark.asyncio
async def test_router_model_loading():
    router = ModelRouter()
    models = router.list_all_models()
    assert len(models) >= 6
    providers = {m.provider for m in models}
    assert "openai" in providers
    assert "anthropic" in providers
    assert "gemini" in providers
    assert "groq" in providers


@pytest.mark.asyncio
async def test_router_capability_filtering(db_session):
    router = ModelRouter()
    # Force openai configured for test
    provider_registry.get_provider("openai", api_key="test-key")

    # Request vision capability
    candidates = await router.get_ranked_candidates(
        session=db_session,
        required_capabilities={"vision": True},
    )
    for c in candidates:
        assert c.capabilities.vision is True
