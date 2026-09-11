"""
Generic OpenAI-compatible Adapter.
Connects to OpenRouter, Perplexity, Together AI, Ollama, vLLM, or any OpenAI-compatible API.
"""
from typing import Optional
from config.settings import settings
from providers.openai.base_openai_compatible import BaseOpenAICompatibleProvider


class GenericOpenAIProvider(BaseOpenAICompatibleProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        key = api_key or settings.GENERIC_OPENAI_API_KEY
        url = base_url or settings.GENERIC_OPENAI_BASE_URL or "https://openrouter.ai/api/v1"
        super().__init__(
            provider_name="generic_openai",
            api_key=key,
            base_url=url,
        )
