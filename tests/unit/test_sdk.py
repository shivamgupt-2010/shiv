"""
Unit tests for ShivAI Python SDK.
"""
import pytest
import respx
import httpx
from shivai import (
    ShivAI,
    AsyncShivAI,
    ChatResponse,
    StreamChunk,
    AuthenticationError,
    RateLimitError,
)

BASE_URL = "http://localhost:8000/api/v1"


def test_sdk_initialization():
    client = ShivAI(api_key="test-key", base_url=BASE_URL)
    assert client.api_key == "test-key"
    assert client.base_url == BASE_URL
    assert client.headers["X-API-Key"] == "test-key"


@respx.mock
def test_sync_chat_create():
    client = ShivAI(api_key="test-key", base_url=BASE_URL)

    respx.post(f"{BASE_URL}/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "request_id": "req-sdk-1",
                "assistant": "shivai",
                "content": "Hello from ShivAI SDK!",
                "model": {"provider": "gemini", "model": "gemini-2.5-flash"},
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                "finish_reason": "stop",
                "latency_ms": 250.0,
                "metadata": {"conversation_id": "conv-sdk-1"},
            },
        )
    )

    response = client.chat.create("Hello ShivAI")
    assert isinstance(response, ChatResponse)
    assert response.assistant == "shivai"
    assert response.content == "Hello from ShivAI SDK!"
    assert response.conversation_id == "conv-sdk-1"
    assert response.model.provider == "gemini"


@respx.mock
def test_sync_chat_stream():
    client = ShivAI(api_key="test-key", base_url=BASE_URL)

    stream_content = [
        'data: {"request_id": "req-1", "assistant": "shivai", "delta": "Hello "}\n\n',
        'data: {"request_id": "req-1", "assistant": "shivai", "delta": "world!"}\n\n',
        'data: [DONE]\n\n',
    ]

    respx.post(f"{BASE_URL}/chat/stream").mock(
        return_value=httpx.Response(200, text="".join(stream_content), headers={"content-type": "text/event-stream"})
    )

    chunks = list(client.chat.stream("Stream a reply"))
    assert len(chunks) == 2
    assert chunks[0].delta == "Hello "
    assert chunks[1].delta == "world!"


@respx.mock
def test_sync_memory_operations():
    client = ShivAI(api_key="test-key", base_url=BASE_URL)

    # 1. Remember
    respx.post(f"{BASE_URL}/memory").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "mem-1",
                "key": "framework",
                "value": "FastAPI",
                "category": "preference",
                "importance": 0.8,
                "confidence": 1.0,
                "source": "user_explicit",
                "created_at": "2026-09-03T18:00:00Z",
            },
        )
    )
    mem = client.memory.remember(key="framework", value="FastAPI", category="preference", importance=0.8)
    assert mem.key == "framework"
    assert mem.value == "FastAPI"

    # 2. Recall
    respx.get(f"{BASE_URL}/memory").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "mem-1",
                    "key": "framework",
                    "value": "FastAPI",
                    "category": "preference",
                    "importance": 0.8,
                    "confidence": 1.0,
                    "source": "user_explicit",
                    "created_at": "2026-09-03T18:00:00Z",
                }
            ],
        )
    )
    recalled = client.memory.recall(query="FastAPI")
    assert len(recalled) == 1
    assert recalled[0].key == "framework"


@respx.mock
def test_sdk_error_handling():
    client = ShivAI(api_key="bad-key", base_url=BASE_URL)

    # 401 Auth Error
    respx.post(f"{BASE_URL}/chat").mock(
        return_value=httpx.Response(401, json={"error": {"code": "UNAUTHORIZED", "message": "Invalid API key."}})
    )
    with pytest.raises(AuthenticationError) as exc:
        client.chat.create("Hello")
    assert "Invalid API key" in exc.value.message

    # 429 Rate Limit
    respx.post(f"{BASE_URL}/chat").mock(
        return_value=httpx.Response(
            429,
            headers={"retry-after": "45"},
            json={"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests."}},
        )
    )
    with pytest.raises(RateLimitError) as exc:
        client.chat.create("Hello again")
    assert exc.value.retry_after == 45


@pytest.mark.asyncio
@respx.mock
async def test_async_chat_create():
    async_client = AsyncShivAI(api_key="test-key", base_url=BASE_URL)

    respx.post(f"{BASE_URL}/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "request_id": "req-async-1",
                "assistant": "shivai",
                "content": "Async ShivAI response!",
                "model": {"provider": "gemini", "model": "gemini-2.5-flash"},
                "usage": {"input_tokens": 8, "output_tokens": 4, "total_tokens": 12},
                "finish_reason": "stop",
                "latency_ms": 190.0,
                "metadata": {},
            },
        )
    )

    response = await async_client.chat.create("Async query")
    assert response.content == "Async ShivAI response!"
