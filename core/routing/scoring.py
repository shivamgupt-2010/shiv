"""
ShivAI Deterministic Model Scoring Engine.
Computes routing scores based on task requirements, model capabilities,
provider health, latency telemetry, priority, and user-specified routing mode.
"""
from enum import Enum
from typing import Dict, Any, Optional
from core.routing.registry import ModelInfo
from core.resilience.circuit_breaker import CircuitState


class RoutingMode(str, Enum):
    AUTO = "auto"
    FASTEST = "fastest"
    QUALITY = "quality"
    BALANCED = "balanced"
    SPECIFIC = "specific"


class ScoringEngine:
    """Calculates deterministic composite scores for model candidates."""

    @staticmethod
    def calculate_score(
        model: ModelInfo,
        mode: RoutingMode = RoutingMode.AUTO,
        circuit_state: CircuitState = CircuitState.CLOSED,
        failure_count: int = 0,
        average_latency_ms: float = 0.0,
        required_capabilities: Optional[Dict[str, bool]] = None,
        preferred_provider: Optional[str] = None,
    ) -> float:
        """
        Calculates a deterministic numerical score for ranking model candidates.
        
        Score components:
        1. Base priority (0-100)
        2. Mode weights (speed, quality, cost)
        3. Health penalties (circuit state, recent failures)
        4. Latency factor
        5. Capability bonus
        6. Provider affinity bonus
        """
        # 1. Base Priority Score
        score = float(model.priority)

        # 2. Capability bonuses
        req_caps = required_capabilities or {}
        if req_caps.get("reasoning") and model.capabilities.reasoning:
            score += 15.0
        if req_caps.get("coding") and model.capabilities.coding:
            score += 10.0
        if req_caps.get("vision") and model.capabilities.vision:
            score += 15.0
        if req_caps.get("tools") and model.capabilities.tools:
            score += 5.0

        # 3. Mode Weighting
        if mode == RoutingMode.FASTEST:
            # Heavily weight speed and low latency
            score += (model.speed_score * 0.8)
            score += (model.cost_score * 0.2)
        elif mode == RoutingMode.QUALITY:
            # Heavily weight intelligence, reasoning, and quality score
            score += (model.quality_score * 0.9)
            if model.cost_tier == "high":
                score += 5.0  # High-tier models favored in quality mode
        elif mode == RoutingMode.BALANCED:
            # Equal triad between speed, quality, and cost efficiency
            score += (model.quality_score * 0.35)
            score += (model.speed_score * 0.35)
            score += (model.cost_score * 0.30)
        else:  # AUTO / default
            score += (model.quality_score * 0.4)
            score += (model.speed_score * 0.3)
            score += (model.cost_score * 0.2)

        # 4. Preferred Provider Bonus
        if preferred_provider and model.provider == preferred_provider:
            score += 25.0

        # 5. Circuit Breaker Health Penalty
        if circuit_state == CircuitState.OPEN:
            return -1000.0  # Open circuit breaker disqualifies the model
        elif circuit_state == CircuitState.HALF_OPEN:
            score -= 40.0   # Demote half-open models behind healthy alternatives

        # 6. Failure History Penalty
        if failure_count > 0:
            score -= min(30.0, failure_count * 6.0)

        # 7. Latency Penalty
        if average_latency_ms > 0:
            # Penalty for every 500ms above 1 second
            latency_sec = average_latency_ms / 1000.0
            if latency_sec > 1.0:
                score -= min(25.0, (latency_sec - 1.0) * 10.0)

        return round(score, 2)
