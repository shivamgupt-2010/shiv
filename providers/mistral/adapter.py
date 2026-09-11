"""
Mistral AI Provider Adapter (Mistral Large, Codestral, Mistral Small).
"""
from typing import Optional
from config.settings import settings
from providers.openai.base_openai_compatible import BaseOpenAICompatibleProvider


class MistralProvider(BaseOpenAICompatibleProvider):
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or settings.MISTRAL_API_KEY
        super().__init__(
            provider_name="mistral",
            api_key=key,
            base_url="https://api.mistral.ai/v1",
        )
