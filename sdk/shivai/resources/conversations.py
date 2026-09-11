"""
ShivAI SDK Conversations Resource (Sync & Async).
"""
from typing import Optional, List
import httpx
from sdk.shivai.types import ConversationItem
from sdk.shivai.resources.chat import _handle_error_response


class ConversationsResource:
    """Synchronous conversation thread management."""

    def __init__(self, client):
        self._client = client

    def list(self, limit: int = 50, offset: int = 0) -> List[ConversationItem]:
        url = f"{self._client.base_url}/conversations"
        params = {"limit": limit, "offset": offset}
        with httpx.Client(timeout=self._client.timeout) as http:
            resp = http.get(url, headers=self._client.headers, params=params)
            if resp.status_code != 200:
                _handle_error_response(resp)
            return [ConversationItem(**item) for item in resp.json()]

    def get(self, conversation_id: str) -> ConversationItem:
        url = f"{self._client.base_url}/conversations/{conversation_id}"
        with httpx.Client(timeout=self._client.timeout) as http:
            resp = http.get(url, headers=self._client.headers)
            if resp.status_code != 200:
                _handle_error_response(resp)
            return ConversationItem(**resp.json())

    def create(self, title: Optional[str] = "New Conversation") -> ConversationItem:
        url = f"{self._client.base_url}/conversations"
        payload = {"title": title}
        with httpx.Client(timeout=self._client.timeout) as http:
            resp = http.post(url, headers=self._client.headers, json=payload)
            if resp.status_code not in (200, 201):
                _handle_error_response(resp)
            return ConversationItem(**resp.json())


class AsyncConversationsResource:
    """Asynchronous conversation thread management."""

    def __init__(self, client):
        self._client = client

    async def list(self, limit: int = 50, offset: int = 0) -> List[ConversationItem]:
        url = f"{self._client.base_url}/conversations"
        params = {"limit": limit, "offset": offset}
        async with httpx.AsyncClient(timeout=self._client.timeout) as http:
            resp = await http.get(url, headers=self._client.headers, params=params)
            if resp.status_code != 200:
                _handle_error_response(resp)
            return [ConversationItem(**item) for item in resp.json()]

    async def get(self, conversation_id: str) -> ConversationItem:
        url = f"{self._client.base_url}/conversations/{conversation_id}"
        async with httpx.AsyncClient(timeout=self._client.timeout) as http:
            resp = await http.get(url, headers=self._client.headers)
            if resp.status_code != 200:
                _handle_error_response(resp)
            return ConversationItem(**resp.json())

    async def create(self, title: Optional[str] = "New Conversation") -> ConversationItem:
        url = f"{self._client.base_url}/conversations"
        payload = {"title": title}
        async with httpx.AsyncClient(timeout=self._client.timeout) as http:
            resp = await http.post(url, headers=self._client.headers, json=payload)
            if resp.status_code not in (200, 201):
                _handle_error_response(resp)
            return ConversationItem(**resp.json())
