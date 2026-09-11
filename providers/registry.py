"""
Provider Registry and Factory.
Maintains available adapters and handles dynamic registration.
"""
from typing import Dict, Type, Optional, List
from providers.base import AIProvider
from providers.openai import OpenAIProvider
from providers.anthropic import AnthropicProvider
from providers.gemini import GeminiProvider
from providers.groq import GroqProvider
from providers.deepseek import DeepSeekProvider
from providers.mistral import MistralProvider
from providers.generic_openai import GenericOpenAIProvider


class ProviderRegistry:
    def __init__(self):
        self._provider_classes: Dict[str, Type[AIProvider]] = {}
        self._provider_instances: Dict[str, AIProvider] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register("openai", OpenAIProvider)
        self.register("anthropic", AnthropicProvider)
        self.register("gemini", GeminiProvider)
        self.register("groq", GroqProvider)
        self.register("deepseek", DeepSeekProvider)
        self.register("mistral", MistralProvider)
        self.register("generic_openai", GenericOpenAIProvider)

    def register(self, name: str, provider_cls: Type[AIProvider]) -> None:
        """Registers a provider adapter class."""
        self._provider_classes[name.lower()] = provider_cls

    def get_provider(self, name: str, api_key: Optional[str] = None) -> AIProvider:
        """Returns or creates a provider adapter instance."""
        key = name.lower()
        if key not in self._provider_classes:
            raise ValueError(f"Unknown provider '{name}'. Available: {list(self._provider_classes.keys())}")

        if api_key:
            inst = self._provider_classes[key](api_key=api_key)
            self._provider_instances[key] = inst
            return inst

        if key not in self._provider_instances:
            self._provider_instances[key] = self._provider_classes[key]()
        return self._provider_instances[key]

    def list_registered(self) -> List[str]:
        return list(self._provider_classes.keys())

    def list_configured(self) -> List[str]:
        configured = []
        for name in self.list_registered():
            try:
                prov = self.get_provider(name)
                if prov.is_configured:
                    configured.append(name)
            except Exception:
                pass
        return configured


provider_registry = ProviderRegistry()
