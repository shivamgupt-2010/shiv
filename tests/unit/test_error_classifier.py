"""
Unit tests for Provider Error Normalization.
"""
import httpx
from providers.errors import ErrorCategory
from providers.openai.adapter import OpenAIProvider


def test_auth_error_classification():
    provider = OpenAIProvider(api_key="test-key")
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status_code=401, text='{"error": {"message": "Invalid API key"}}', request=request)
    http_error = httpx.HTTPStatusError("Auth error", request=request, response=response)

    normalized = provider.normalize_error(http_error)
    assert normalized.category == ErrorCategory.AUTH_ERROR
    assert normalized.status_code == 401
    assert normalized.provider == "openai"


def test_quota_exhausted_classification():
    provider = OpenAIProvider(api_key="test-key")
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(
        status_code=429,
        text='{"error": {"message": "You exceeded your current quota, please check your plan and billing details."}}',
        request=request,
    )
    http_error = httpx.HTTPStatusError("Quota error", request=request, response=response)

    normalized = provider.normalize_error(http_error)
    assert normalized.category == ErrorCategory.QUOTA_EXCEEDED


def test_rate_limit_classification():
    provider = OpenAIProvider(api_key="test-key")
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    headers = {"retry-after": "30"}
    response = httpx.Response(
        status_code=429,
        text='{"error": {"message": "Rate limit reached for requests"}}',
        headers=headers,
        request=request,
    )
    http_error = httpx.HTTPStatusError("Rate limit error", request=request, response=response)

    normalized = provider.normalize_error(http_error)
    assert normalized.category == ErrorCategory.RATE_LIMIT
    assert normalized.retry_after == 30


def test_timeout_classification():
    provider = OpenAIProvider(api_key="test-key")
    timeout_err = httpx.ReadTimeout("Read timed out")
    normalized = provider.normalize_error(timeout_err)
    assert normalized.category == ErrorCategory.TIMEOUT


def test_context_too_large_classification():
    provider = OpenAIProvider(api_key="test-key")
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(
        status_code=400,
        text='{"error": {"message": "This model maximum context length is 128000 tokens"}}',
        request=request,
    )
    http_error = httpx.HTTPStatusError("Context error", request=request, response=response)

    normalized = provider.normalize_error(http_error)
    assert normalized.category == ErrorCategory.CONTEXT_TOO_LARGE
