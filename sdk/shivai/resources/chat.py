"""
ShivAI SDK Chat Resource (Sync & Async).
"""
import json
from typing import Optional, Dict, Any, Iterator, AsyncIterator
import httpx
from sdk.shivai.types import ChatResponse, StreamChunk
from sdk.shivai.exceptions import (
    ShivAIError,
    AuthenticationError,
    RateLimitError,
    ServiceUnavailableError,
)


def _handle_error_response(resp: httpx.Response) -> None:
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}

    msg = body.get("error", {}).get("message") or resp.text
    if resp.status_code == 401:
        raise AuthenticationError(msg, status_code=401, response_body=body)
    elif resp.status_code == 429:
        retry_header = resp.headers.get("retry-after")
        retry_after = int(retry_header) if retry_header and retry_header.isdigit() else None
        raise RateLimitError(msg, retry_after=retry_after, status_code=429, response_body=body)
    elif resp.status_code == 503:
        raise ServiceUnavailableError(msg, status_code=503, response_body=body)
    else:
        raise ShivAIError(f"HTTP {resp.status_code}: {msg}", status_code=resp.status_code, response_body=body)


class ChatResource:
    """Synchronous Chat operations."""

    def __init__(self, client):
        self._client = client

    def create(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        agent: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        url = f"{self._client.base_url}/chat"
        payload = {
            "message": message,
            "conversation_id": conversation_id,
            "agent": agent,
            "custom_instructions": custom_instructions,
            "preferred_provider": preferred_provider,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        with httpx.Client(timeout=self._client.timeout) as http:
            resp = http.post(url, headers=self._client.headers, json=payload)
            if resp.status_code != 200:
                _handle_error_response(resp)
            return ChatResponse(**resp.json())

    def stream(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        agent: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Iterator[StreamChunk]:
        url = f"{self._client.base_url}/chat/stream"
        payload = {
            "message": message,
            "conversation_id": conversation_id,
            "agent": agent,
            "custom_instructions": custom_instructions,
            "preferred_provider": preferred_provider,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        with httpx.Client(timeout=self._client.timeout) as http:
            with http.stream("POST", url, headers=self._client.headers, json=payload) as resp:
                if resp.status_code != 200:
                    _handle_error_response(resp)

                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_dict = json.loads(data_str)
                        if "error" in chunk_dict:
                            raise ShivAIError(chunk_dict["error"].get("message", "Streaming error"))
                        yield StreamChunk(**chunk_dict)
                    except json.JSONDecodeError:
                        continue


class AsyncChatResource:
    """Asynchronous Chat operations."""

    def __init__(self, client):
        self._client = client

    async def create(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        agent: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        url = f"{self._client.base_url}/chat"
        payload = {
            "message": message,
            "conversation_id": conversation_id,
            "agent": agent,
            "custom_instructions": custom_instructions,
            "preferred_provider": preferred_provider,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=self._client.timeout) as http:
            resp = await http.post(url, headers=self._client.headers, json=payload)
            if resp.status_code != 200:
                _handle_error_response(resp)
            return ChatResponse(**resp.json())

    async def stream(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        agent: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[StreamChunk]:
        url = f"{self._client.base_url}/chat/stream"
        payload = {
            "message": message,
            "conversation_id": conversation_id,
            "agent": agent,
            "custom_instructions": custom_instructions,
            "preferred_provider": preferred_provider,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=self._client.timeout) as http:
            async with http.stream("POST", url, headers=self._client.headers, json=payload) as resp:
                if resp.status_code != 200:
                    _handle_error_response(resp)

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_dict = json.loads(data_str)
                        if "error" in chunk_dict:
                            raise ShivAIError(chunk_dict["error"].get("message", "Streaming error"))
                        yield StreamChunk(**chunk_dict)
                    except json.JSONDecodeError:
                        continue
