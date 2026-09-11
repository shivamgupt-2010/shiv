"""
OpenAI Provider Adapter.
"""
from typing import Optional
from config.settings import settings
from providers.openai.base_openai_compatible import BaseOpenAICompatibleProvider


class OpenAIProvider(BaseOpenAICompatibleProvider):
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or settings.OPENAI_API_KEY
        super().__init__(
            provider_name="openai",
            api_key=key,
            base_url="https://api.openai.com/v1",
        )
