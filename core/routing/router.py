"""
ShivAI Intelligent Model Router.
Scores, filters, and ranks models dynamically based on task requirements,
capabilities, provider credentials, real-time circuit-breaker health, and routing mode.
"""
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from providers.registry import provider_registry
from core.routing.registry import model_registry, ModelInfo, ModelCapabilities
from core.routing.scoring import RoutingMode, ScoringEngine
from core.resilience.circuit_breaker import circuit_breaker_registry, CircuitState
from database.repositories.provider_repo import ProviderRepository

# Backward compatibility alias
ModelConfig = ModelInfo


class RoutingDecision(BaseModel):
    selected_model: ModelInfo
    ranked_candidates: List[ModelInfo]
    mode: RoutingMode
    routing_reason: str
    scores: Dict[str, float] = Field(default_factory=dict)


class ModelRouter:
    """Intelligent scoring and selection engine for AI models."""

    def __init__(self, config_path: Optional[Path] = None):
        self.registry = model_registry
        if config_path:
            self.registry.config_path = config_path
            self.registry.load()

    def list_all_models(self) -> List[ModelInfo]:
        return self.registry.list_all(enabled_only=False)

    async def route_request(
        self,
        mode: Union[str, RoutingMode] = RoutingMode.AUTO,
        specific_model_name: Optional[str] = None,
        required_capabilities: Optional[Dict[str, bool]] = None,
        min_context_limit: int = 0,
        preferred_provider: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> RoutingDecision:
        """
        V2 Intelligent Routing Engine:
        Evaluates models and returns the optimal selected model along with ranked fallbacks.
        """
        if isinstance(mode, str):
            try:
                mode = RoutingMode(mode.lower())
            except ValueError:
                mode = RoutingMode.AUTO

        # 1. SPECIFIC Mode: Explicit user model selection
        if mode == RoutingMode.SPECIFIC or specific_model_name:
            target_name = specific_model_name or ""
            target = self.registry.get(target_name)
            if not target:
                from providers.errors import ProviderError, ErrorCategory
                raise ProviderError(
                    category=ErrorCategory.MODEL_UNAVAILABLE,
                    message=f"Requested model '{target_name}' is not registered in ShivAI.",
                    provider="unknown",
                    model=target_name,
                    status_code=404,
                )

            if not target.enabled:
                from providers.errors import ProviderError, ErrorCategory
                raise ProviderError(
                    category=ErrorCategory.MODEL_UNAVAILABLE,
                    message=f"Requested model '{target_name}' is currently disabled in ShivAI configuration.",
                    provider=target.provider,
                    model=target_name,
                    status_code=400,
                )

            # Check if provider is configured
            if target.provider not in provider_registry.list_configured():
                from providers.errors import ProviderError, ErrorCategory
                raise ProviderError(
                    category=ErrorCategory.AUTH_ERROR,
                    message=f"No API key configured for provider '{target.provider}' required by model '{target_name}'.",
                    provider=target.provider,
                    model=target_name,
                    status_code=401,
                )

            # Check circuit breaker
            breaker = await circuit_breaker_registry.get_or_create(target.provider)
            if not await breaker.can_execute():
                from providers.errors import ProviderError, ErrorCategory
                raise ProviderError(
                    category=ErrorCategory.MODEL_UNAVAILABLE,
                    message=f"Provider '{target.provider}' for model '{target_name}' is temporarily unavailable (circuit breaker OPEN).",
                    provider=target.provider,
                    model=target_name,
                    status_code=503,
                )

            return RoutingDecision(
                selected_model=target,
                ranked_candidates=[target],
                mode=RoutingMode.SPECIFIC,
                routing_reason=f"Explicitly requested model: {target.display_name}",
                scores={target.model_id: 100.0},
            )

        # 2. Dynamic Ranked Candidate Selection (AUTO, FASTEST, QUALITY, BALANCED)
        candidates = await self.get_ranked_candidates(
            session=session,
            required_capabilities=required_capabilities,
            min_context_limit=min_context_limit,
            preferred_provider=preferred_provider,
            mode=mode,
        )

        if not candidates:
            from providers.errors import ProviderError, ErrorCategory
            raise ProviderError(
                category=ErrorCategory.MODEL_UNAVAILABLE,
                message="No eligible AI models are currently available matching required capabilities and health criteria.",
                provider="router",
                status_code=503,
            )

        return RoutingDecision(
            selected_model=candidates[0],
            ranked_candidates=candidates,
            mode=mode,
            routing_reason=f"Selected highest scoring model under '{mode.value}' mode: {candidates[0].display_name}",
        )

    async def get_ranked_candidates(
        self,
        session: Optional[AsyncSession] = None,
        required_capabilities: Optional[Dict[str, bool]] = None,
        min_context_limit: int = 0,
        preferred_provider: Optional[str] = None,
        mode: Union[str, RoutingMode] = RoutingMode.AUTO,
    ) -> List[ModelInfo]:
        """
        Ranks models dynamically:
        1. Filters unconfigured providers (missing API keys).
        2. Filters disabled models.
        3. Filters tripped circuit breakers (OPEN).
        4. Filters capability mismatches.
        5. Filters context window constraints.
        6. Computes deterministic score based on mode, speed, quality, cost, and health.
        """
        if isinstance(mode, str):
            try:
                mode = RoutingMode(mode.lower())
            except ValueError:
                mode = RoutingMode.AUTO

        configured_providers = set(provider_registry.list_configured())
        req_caps = required_capabilities or {}
        candidates: List[ModelInfo] = []
        candidate_scores: Dict[str, float] = {}

        for model in self.registry.list_all(enabled_only=True):
            # 1. API key existence
            if model.provider not in configured_providers:
                continue

            # 2. Circuit breaker check
            breaker = await circuit_breaker_registry.get_or_create(model.provider)
            if not await breaker.can_execute():
                continue

            # 3. DB Provider availability check (if DB session provided)
            if session:
                try:
                    repo = ProviderRepository(session)
                    is_avail = await repo.is_provider_available(model.provider)
                    if not is_avail:
                        continue
                except Exception:
                    pass

            # 4. Capability filtering
            caps_dict = model.capabilities.model_dump()
            incompatible = False
            for cap_name, cap_required in req_caps.items():
                if cap_required and not caps_dict.get(cap_name, False):
                    incompatible = True
                    break
            if incompatible:
                continue

            # 5. Context limit filtering
            if model.context_window < min_context_limit:
                continue

            # 6. Calculate deterministic score
            score = ScoringEngine.calculate_score(
                model=model,
                mode=mode,
                circuit_state=breaker.state,
                failure_count=breaker.failure_count,
                required_capabilities=req_caps,
                preferred_provider=preferred_provider,
            )

            if score > -500:  # Not disqualified
                candidates.append(model)
                candidate_scores[model.model_id] = score

        # Sort descending by calculated score
        candidates.sort(key=lambda m: candidate_scores.get(m.model_id, 0.0), reverse=True)
        return candidates


# Global Model Router Instance
model_router = ModelRouter()
