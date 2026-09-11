"""
ShivAI SDK Models Resource (Sync & Async).
"""
from typing import List, Dict, Any
import httpx
from sdk.shivai.resources.chat import _handle_error_response


class ModelsResource:
    def __init__(self, client):
        self._client = client

    def list(self) -> List[Dict[str, Any]]:
        url = f"{self._client.base_url}/models"
        with httpx.Client(timeout=self._client.timeout) as http:
            resp = http.get(url, headers=self._client.headers)
            if resp.status_code != 200:
                _handle_error_response(resp)
            return resp.json()


class AsyncModelsResource:
    def __init__(self, client):
        self._client = client

    async def list(self) -> List[Dict[str, Any]]:
        url = f"{self._client.base_url}/models"
        async with httpx.AsyncClient(timeout=self._client.timeout) as http:
            resp = await http.get(url, headers=self._client.headers)
            if resp.status_code != 200:
                _handle_error_response(resp)
            return resp.json()
