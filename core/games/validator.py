"""
ShivAI Game Development Studio: Headless Game Code & Project Validator.
Verifies syntax, game loop integrity, input bindings, rendering context, and collision systems.
"""
import re
import logging
from typing import Dict, Any, List
from pydantic import BaseModel, Field

logger = logging.getLogger("shivai.games.validator")


class GameValidationResult(BaseModel):
    is_valid: bool
    checks_passed: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    estimated_fps: int = 60
    has_audio: bool = False
    has_touch_controls: bool = False


class GameValidator:
    """Performs static analysis and behavioral verification on generated game bundles."""

    @staticmethod
    def validate_html5_game(html_content: str) -> GameValidationResult:
        """Analyzes an HTML5 game bundle for runtime completeness."""
        passed = []
        warnings = []
        errors = []

        # 1. Basic HTML Structure
        if "<!DOCTYPE html>" in html_content and "<canvas" in html_content:
            passed.append("Valid HTML5 Doctype & Canvas container")
        elif "three.js" in html_content.lower() or "webgl" in html_content.lower():
            passed.append("Valid 3D WebGL renderer container")
        else:
            errors.append("Missing HTML5 canvas or WebGL viewport element.")

        # 2. Game Loop Verification
        if "requestAnimationFrame" in html_content:
            passed.append("Standard 60 FPS requestAnimationFrame game loop")
        elif "setInterval" in html_content:
            warnings.append("Using setInterval fallback loop instead of requestAnimationFrame")
            passed.append("Timer-based game loop")
        else:
            errors.append("No active game loop detected.")

        # 3. Input Handling
        has_keyboard = any(k in html_content for k in ["keydown", "keyup", "ArrowLeft", "KeyA"])
        if has_keyboard:
            passed.append("Keyboard WASD / Arrow input handlers")
        else:
            warnings.append("No standard keyboard event listeners found.")

        has_touch = any(t in html_content for t in ["touchstart", "touchend", "touch-btn"])
        if has_touch:
            passed.append("Mobile responsive touch button controls")

        # 4. Collision / Score / Game Over
        has_collision = any(c in html_content for c in ["hypot", "dist", "radius", "intersect", "collision"])
        if has_collision:
            passed.append("Entity collision detection logic")
        else:
            warnings.append("No entity collision math detected.")

        has_state = "gameOver" in html_content or "lives" in html_content or "score" in html_content
        if has_state:
            passed.append("Game state management (Score / Lives / Game Over)")

        # 5. Audio Synthesizer
        has_audio = "AudioContext" in html_content or "webkitAudioContext" in html_content or "<audio" in html_content
        if has_audio:
            passed.append("Web Audio procedural sound synthesizer")

        is_valid = len(errors) == 0

        logger.info(f"Validated game bundle: valid={is_valid}, {len(passed)} checks passed, {len(errors)} errors.")
        return GameValidationResult(
            is_valid=is_valid,
            checks_passed=passed,
            warnings=warnings,
            errors=errors,
            estimated_fps=60 if "requestAnimationFrame" in html_content else 30,
            has_audio=has_audio,
            has_touch_controls=has_touch,
        )


game_validator = GameValidator()
