"""
ShivAI Central Model Registry.
Manages metadata, capabilities, quality, speed, cost scores, and availability for all AI models.
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import yaml
from pydantic import BaseModel, Field, model_validator
from config.settings import settings


class ModelCapabilities(BaseModel):
    reasoning: bool = True
    vision: bool = False
    tools: bool = True
    streaming: bool = True
    coding: bool = True
    structured_output: bool = True
    image_generation: bool = False
    video_generation: bool = False
    audio_generation: bool = False


class ModelInfo(BaseModel):
    model_id: str
    provider: str
    model_name: str
    display_name: str = ""
    enabled: bool = True
    priority: int = 50
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)
    context_window: int = 32000
    max_output_tokens: int = 4096
    supports_streaming: bool = True
    supports_structured_output: bool = True
    speed_score: float = 70.0   # 0 to 100 (higher = faster)
    quality_score: float = 80.0 # 0 to 100 (higher = better output quality)
    cost_score: float = 80.0    # 0 to 100 (higher = cheaper/lower cost)
    cost_tier: str = "low"      # low, medium, high

    @model_validator(mode="before")
    @classmethod
    def remap_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "id" in data and "model_id" not in data:
                data["model_id"] = data["id"]
            if "model" in data and "model_name" not in data:
                data["model_name"] = data["model"]
            if "context_limit" in data and "context_window" not in data:
                data["context_window"] = data["context_limit"]
            if "model_id" not in data and "model_name" in data:
                data["model_id"] = f"{data.get('provider', 'ai')}_{data['model_name']}"
            elif "model_name" not in data and "model_id" in data:
                data["model_name"] = data["model_id"]
        return data

    @property
    def capability_list(self) -> List[str]:
        return [k for k, v in self.capabilities.model_dump().items() if v]

    @property
    def id(self) -> str:
        """Backward compatibility alias for model_id."""
        return self.model_id

    @property
    def model(self) -> str:
        """Backward compatibility alias for model_name."""
        return self.model_name

    @property
    def context_limit(self) -> int:
        """Backward compatibility alias for context_window."""
        return self.context_window


# Default speed/quality/cost score profiles by model pattern
DEFAULT_SCORE_PROFILES: Dict[str, Dict[str, float]] = {
    "groq": {"speed_score": 98.0, "quality_score": 85.0, "cost_score": 98.0},
    "gemini-2.5-flash": {"speed_score": 92.0, "quality_score": 90.0, "cost_score": 95.0},
    "gemini-flash-latest": {"speed_score": 92.0, "quality_score": 90.0, "cost_score": 95.0},
    "gemini-2.5-pro": {"speed_score": 75.0, "quality_score": 95.0, "cost_score": 70.0},
    "gpt-4o": {"speed_score": 78.0, "quality_score": 95.0, "cost_score": 60.0},
    "gpt-4o-mini": {"speed_score": 90.0, "quality_score": 86.0, "cost_score": 92.0},
    "claude-3-5-sonnet": {"speed_score": 74.0, "quality_score": 97.0, "cost_score": 55.0},
    "claude-3-5-haiku": {"speed_score": 92.0, "quality_score": 87.0, "cost_score": 90.0},
    "deepseek-reasoner": {"speed_score": 65.0, "quality_score": 96.0, "cost_score": 85.0},
    "deepseek-chat": {"speed_score": 85.0, "quality_score": 88.0, "cost_score": 95.0},
    "codestral": {"speed_score": 88.0, "quality_score": 92.0, "cost_score": 90.0},
    "mistral-large": {"speed_score": 72.0, "quality_score": 91.0, "cost_score": 65.0},
}


class ModelRegistry:
    """Central store for model definitions, configurations, and queries."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or settings.MODELS_CONFIG_PATH
        self._models: Dict[str, ModelInfo] = {}
        self.load()

    def load(self) -> None:
        """Parses model declarations from YAML configuration."""
        self._models.clear()
        if not self.config_path or not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            raw_models = data.get("models", [])
            for item in raw_models:
                m_id = item.get("id", "")
                provider = item.get("provider", "")
                model_name = item.get("model", "")
                
                # Derive scores from profiles or defaults
                speed = 75.0
                quality = 80.0
                cost = 80.0
                for pattern, profile in DEFAULT_SCORE_PROFILES.items():
                    if pattern in m_id or pattern in model_name or pattern == provider:
                        speed = profile.get("speed_score", speed)
                        quality = profile.get("quality_score", quality)
                        cost = profile.get("cost_score", cost)
                        break

                caps_dict = item.get("capabilities", {})
                caps = ModelCapabilities(
                    reasoning=caps_dict.get("reasoning", True),
                    vision=caps_dict.get("vision", False),
                    tools=caps_dict.get("tools", True),
                    streaming=caps_dict.get("streaming", True),
                    coding=caps_dict.get("coding", True),
                    structured_output=caps_dict.get("structured_output", True),
                    image_generation=caps_dict.get("image_generation", False),
                    video_generation=caps_dict.get("video_generation", False),
                    audio_generation=caps_dict.get("audio_generation", False),
                )

                info = ModelInfo(
                    model_id=m_id,
                    provider=provider,
                    model_name=model_name,
                    display_name=item.get("display_name", f"{provider.capitalize()} - {model_name}"),
                    enabled=item.get("status", "active") == "active",
                    priority=item.get("priority", 50),
                    capabilities=caps,
                    context_window=item.get("context_limit", 32000),
                    max_output_tokens=item.get("max_output_tokens", 4096),
                    supports_streaming=caps.streaming,
                    supports_structured_output=caps.structured_output,
                    speed_score=item.get("speed_score", speed),
                    quality_score=item.get("quality_score", quality),
                    cost_score=item.get("cost_score", cost),
                    cost_tier=item.get("cost_tier", "low"),
                )
                self._models[m_id] = info
        except Exception as e:
            import logging
            logging.getLogger("shivai.registry").error(f"Failed to load models config from {self.config_path}: {e}")

    def get(self, model_id_or_name: str) -> Optional[ModelInfo]:
        """Looks up a model by ID or exact model name."""
        if model_id_or_name in self._models:
            return self._models[model_id_or_name]
        
        for m in self._models.values():
            if m.model_name == model_id_or_name or m.model_id == model_id_or_name:
                return m
        return None

    def get_model(self, model_id_or_name: str) -> Optional[ModelInfo]:
        """Alias for get()."""
        return self.get(model_id_or_name)

    def list_all(self, enabled_only: bool = True) -> List[ModelInfo]:
        """Returns all registered models."""
        models = list(self._models.values())
        if enabled_only:
            models = [m for m in models if m.enabled]
        return models

    def list_for_provider(self, provider: str, enabled_only: bool = True) -> List[ModelInfo]:
        """Lists models belonging to a specific provider."""
        return [m for m in self.list_all(enabled_only=enabled_only) if m.provider == provider]

    def register_model(self, info: ModelInfo) -> None:
        """Dynamically registers or overrides a model."""
        self._models[info.model_id] = info


# Global Registry Instance
model_registry = ModelRegistry()
