"""
Comprehensive Provider Failure & Fallback Simulations.
Simulates Quota Exhaustion, Rate Limits, Timeouts, Auth Failures, and All-Provider Outages.
"""
import pytest
import respx
import httpx
from core.routing.fallback_handler import FallbackHandler, ShivAIServiceException
from core.routing.router import ModelConfig, ModelCapabilities
from providers.registry import provider_registry


@pytest.fixture
def mock_candidates():
    """Two candidate models: primary (OpenAI) and secondary (Groq)."""
    # Ensure provider adapters are configured with dummy keys for testing
    provider_registry.get_provider("openai", api_key="test-openai-key")
    provider_registry.get_provider("groq", api_key="test-groq-key")

    c1 = ModelConfig(
        id="openai_primary",
        provider="openai",
        model="gpt-4o",
        priority=90,
        capabilities=ModelCapabilities(),
    )
    c2 = ModelConfig(
        id="groq_fallback",
        provider="groq",
        model="llama-3.3-70b-versatile",
        priority=80,
        capabilities=ModelCapabilities(),
    )
    return [c1, c2]


@pytest.mark.asyncio
@respx.mock
async def test_normal_request_success(db_session, mock_candidates):
    """Test 1: Normal request -> best available model responds."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Hello from primary model!"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
            },
        )
    )

    handler = FallbackHandler(db_session)
    response = await handler.execute_with_fallback(
        candidates=mock_candidates,
        messages=[{"role": "user", "content": "Hello"}],
        request_id="req-test-1",
    )

    assert response.assistant == "shivai"
    assert response.content == "Hello from primary model!"
    assert response.model.provider == "openai"


@pytest.mark.asyncio
@respx.mock
async def test_fallback_on_quota_exhausted(db_session, mock_candidates):
    """Test 2: Primary provider quota exhausted -> next suitable provider responds."""
    # Primary returns 429 with quota exceeded
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            429,
            json={"error": {"message": "You exceeded your current quota, please check your plan and billing details."}},
        )
    )
    # Secondary succeeds
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Hello from fallback Groq!"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
    )

    handler = FallbackHandler(db_session)
    response = await handler.execute_with_fallback(
        candidates=mock_candidates,
        messages=[{"role": "user", "content": "Hello"}],
        request_id="req-test-quota",
    )

    assert response.assistant == "shivai"
    assert response.content == "Hello from fallback Groq!"
    assert response.model.provider == "groq"


@pytest.mark.asyncio
@respx.mock
async def test_fallback_on_rate_limit(db_session, mock_candidates):
    """Test 3: Primary provider rate-limited -> fallback occurs appropriately."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            429,
            headers={"retry-after": "60"},
            json={"error": {"message": "Rate limit reached for requests per minute."}},
        )
    )
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Response after rate limit fallback"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
            },
        )
    )

    handler = FallbackHandler(db_session)
    response = await handler.execute_with_fallback(
        candidates=mock_candidates,
        messages=[{"role": "user", "content": "Hello"}],
        request_id="req-test-ratelimit",
    )

    assert response.model.provider == "groq"
    assert response.content == "Response after rate limit fallback"


@pytest.mark.asyncio
@respx.mock
async def test_fallback_on_timeout(db_session, mock_candidates):
    """Test 4: Primary provider timeout -> fallback occurs."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=httpx.ReadTimeout("Connection timed out")
    )
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Response after timeout fallback"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
    )

    handler = FallbackHandler(db_session)
    response = await handler.execute_with_fallback(
        candidates=mock_candidates,
        messages=[{"role": "user", "content": "Hello"}],
        request_id="req-test-timeout",
    )

    assert response.model.provider == "groq"
    assert response.content == "Response after timeout fallback"


@pytest.mark.asyncio
@respx.mock
async def test_fallback_on_auth_failure(db_session, mock_candidates):
    """Test 5: Primary provider auth failure -> provider marked unhealthy and fallback occurs."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            401,
            json={"error": {"message": "Incorrect API key provided"}},
        )
    )
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Response after auth failure fallback"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
    )

    handler = FallbackHandler(db_session)
    response = await handler.execute_with_fallback(
        candidates=mock_candidates,
        messages=[{"role": "user", "content": "Hello"}],
        request_id="req-test-auth",
    )

    assert response.model.provider == "groq"
    assert response.content == "Response after auth failure fallback"


@pytest.mark.asyncio
@respx.mock
async def test_all_providers_unavailable(db_session, mock_candidates):
    """Test 6: All providers unavailable -> clean ShivAI error."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="Internal OpenAI Error")
    )
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="Internal Groq Error")
    )

    handler = FallbackHandler(db_session)
    with pytest.raises(ShivAIServiceException) as exc_info:
        await handler.execute_with_fallback(
            candidates=mock_candidates,
            messages=[{"role": "user", "content": "Hello"}],
            request_id="req-test-all-down",
        )

    err = exc_info.value
    assert err.code == "AI_SERVICE_TEMPORARILY_UNAVAILABLE"
    assert "ShivAI could not complete the request right now" in err.message
    assert err.request_id == "req-test-all-down"
