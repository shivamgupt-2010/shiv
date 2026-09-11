"""
DeepSeek Provider Adapter (DeepSeek-V3 & DeepSeek-R1 reasoning models).
"""
from typing import Optional
from config.settings import settings
from providers.openai.base_openai_compatible import BaseOpenAICompatibleProvider


class DeepSeekProvider(BaseOpenAICompatibleProvider):
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or settings.DEEPSEEK_API_KEY
        super().__init__(
            provider_name="deepseek",
            api_key=key,
            base_url="https://api.deepseek.com",
        )
