"""
Intelligent Model Router.
Scores, filters, and ranks models dynamically based on task requirements,
capabilities, provider credentials, and real-time health.
"""
from typing import List, Dict, Any, Optional
import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import settings
from providers.registry import provider_registry
from database.repositories.provider_repo import ProviderRepository


class ModelCapabilities(BaseModel):
    reasoning: bool = True
    vision: bool = False
    tools: bool = True
    streaming: bool = True
    coding: bool = True


class ModelConfig(BaseModel):
    id: str
    provider: str
    model: str
    priority: int = 50
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)
    context_limit: int = 32000
    max_output_tokens: int = 4096
    cost_tier: str = "low"
    status: str = "active"


class ModelRouter:
    """Intelligent scoring and selection engine for AI models."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or settings.MODELS_CONFIG_PATH
        self._models: List[ModelConfig] = []
        self.load_models()

    def load_models(self) -> None:
        """Loads model configurations from YAML file."""
        if not self.config_path.exists():
            self._models = []
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}

        model_list = raw_data.get("models", [])
        self._models = [ModelConfig(**m) for m in model_list]

    def list_all_models(self) -> List[ModelConfig]:
        return list(self._models)

    async def get_ranked_candidates(
        self,
        session: AsyncSession,
        required_capabilities: Optional[Dict[str, bool]] = None,
        min_context_limit: int = 0,
        preferred_provider: Optional[str] = None,
    ) -> List[ModelConfig]:
        """
        Ranks models dynamically:
        1. Filters out unconfigured providers (no API key).
        2. Filters out inactive models.
        3. Filters out providers currently in cooldown, quota exhausted, or auth failed.
        4. Filters by required capabilities (vision, tools, etc.).
        5. Filters by context window size.
        6. Scores and ranks surviving candidates.
        """
        provider_repo = ProviderRepository(session)
        configured_providers = set(provider_registry.list_configured())
        req_caps = required_capabilities or {}

        candidates: List[ModelConfig] = []

        for model in self._models:
            if model.status != "active":
                continue

            # Check if API key is present for provider
            if model.provider not in configured_providers:
                continue

            # Check health & cooldown in database
            try:
                is_available = await provider_repo.is_provider_available(model.provider)
            except Exception:
                is_available = True
            if not is_available:
                continue

            # Capability filtering
            caps_dict = model.capabilities.model_dump()
            incompatible = False
            for cap_name, cap_required in req_caps.items():
                if cap_required and not caps_dict.get(cap_name, False):
                    incompatible = True
                    break
            if incompatible:
                continue

            # Context limit filtering
            if model.context_limit < min_context_limit:
                continue

            candidates.append(model)

        # Score candidates
        def score_model(m: ModelConfig) -> float:
            score = float(m.priority)
            if preferred_provider and m.provider == preferred_provider:
                score += 30.0
            if req_caps.get("reasoning") and m.capabilities.reasoning:
                score += 10.0
            if req_caps.get("coding") and m.capabilities.coding:
                score += 5.0
            # Small bonus for low-cost models when all else is equal
            if m.cost_tier == "low":
                score += 2.0
            return score

        candidates.sort(key=score_model, reverse=True)
        return candidates


model_router = ModelRouter()
