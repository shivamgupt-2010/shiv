"""
ShivAI Official Python Client.
Provides synchronous and asynchronous bindings to the ShivAI AI Backend.
"""
import os
from typing import Optional, Dict
from sdk.shivai.resources import (
    ChatResource,
    AsyncChatResource,
    MemoryResource,
    AsyncMemoryResource,
    ConversationsResource,
    AsyncConversationsResource,
    ModelsResource,
    AsyncModelsResource,
)

DEFAULT_BASE_URL = "http://localhost:8000/api/v1"


class ShivAI:
    """
    Synchronous client for ShivAI.

    Usage:
        from shivai import ShivAI

        client = ShivAI(api_key="...", base_url="http://localhost:8000/api/v1")
        response = client.chat.create("Hello ShivAI")
        print(response.content)

        for chunk in client.chat.stream("Tell me a joke"):
            print(chunk.delta, end="")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key or os.environ.get("SHIVAI_API_KEY", "shivai-test-client-key")
        self.base_url = (base_url or os.environ.get("SHIVAI_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout

        self.chat = ChatResource(self)
        self.memory = MemoryResource(self)
        self.conversations = ConversationsResource(self)
        self.models = ModelsResource(self)

    @property
    def headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        return h


class AsyncShivAI:
    """
    Asynchronous client for ShivAI.

    Usage:
        from shivai import AsyncShivAI

        client = AsyncShivAI(api_key="...", base_url="http://localhost:8000/api/v1")
        response = await client.chat.create("Hello ShivAI")
        print(response.content)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key or os.environ.get("SHIVAI_API_KEY", "shivai-test-client-key")
        self.base_url = (base_url or os.environ.get("SHIVAI_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout

        self.chat = AsyncChatResource(self)
        self.memory = AsyncMemoryResource(self)
        self.conversations = AsyncConversationsResource(self)
        self.models = AsyncModelsResource(self)

    @property
    def headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        return h
