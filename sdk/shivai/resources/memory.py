"""
ShivAI SDK Memory Resource (Sync & Async).
"""
from typing import Optional, List
import httpx
from sdk.shivai.types import MemoryItem
from sdk.shivai.resources.chat import _handle_error_response


class MemoryResource:
    """Synchronous memory operations."""

    def __init__(self, client):
        self._client = client

    def remember(
        self,
        key: str,
        value: str,
        category: str = "general",
        importance: float = 0.5,
    ) -> MemoryItem:
        url = f"{self._client.base_url}/memory"
        payload = {
            "key": key,
            "value": value,
            "category": category,
            "importance": importance,
        }
        with httpx.Client(timeout=self._client.timeout) as http:
            resp = http.post(url, headers=self._client.headers, json=payload)
            if resp.status_code not in (200, 201):
                _handle_error_response(resp)
            return MemoryItem(**resp.json())

    def recall(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryItem]:
        url = f"{self._client.base_url}/memory"
        params = {"limit": limit}
        if query:
            params["query"] = query
        if category:
            params["category"] = category

        with httpx.Client(timeout=self._client.timeout) as http:
            resp = http.get(url, headers=self._client.headers, params=params)
            if resp.status_code != 200:
                _handle_error_response(resp)
            return [MemoryItem(**item) for item in resp.json()]

    def forget(self, memory_id: str) -> bool:
        url = f"{self._client.base_url}/memory/{memory_id}"
        with httpx.Client(timeout=self._client.timeout) as http:
            resp = http.delete(url, headers=self._client.headers)
            if resp.status_code != 200:
                _handle_error_response(resp)
            return True


class AsyncMemoryResource:
    """Asynchronous memory operations."""

    def __init__(self, client):
        self._client = client

    async def remember(
        self,
        key: str,
        value: str,
        category: str = "general",
        importance: float = 0.5,
    ) -> MemoryItem:
        url = f"{self._client.base_url}/memory"
        payload = {
            "key": key,
            "value": value,
            "category": category,
            "importance": importance,
        }
        async with httpx.AsyncClient(timeout=self._client.timeout) as http:
            resp = await http.post(url, headers=self._client.headers, json=payload)
            if resp.status_code not in (200, 201):
                _handle_error_response(resp)
            return MemoryItem(**resp.json())

    async def recall(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryItem]:
        url = f"{self._client.base_url}/memory"
        params = {"limit": limit}
        if query:
            params["query"] = query
        if category:
            params["category"] = category

        async with httpx.AsyncClient(timeout=self._client.timeout) as http:
            resp = await http.get(url, headers=self._client.headers, params=params)
            if resp.status_code != 200:
                _handle_error_response(resp)
            return [MemoryItem(**item) for item in resp.json()]

    async def forget(self, memory_id: str) -> bool:
        url = f"{self._client.base_url}/memory/{memory_id}"
        async with httpx.AsyncClient(timeout=self._client.timeout) as http:
            resp = await http.delete(url, headers=self._client.headers)
            if resp.status_code != 200:
                _handle_error_response(resp)
            return True
