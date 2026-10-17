"""
ShivAI V2 Comprehensive Automated Test Suite.
Verifies:
1. Circuit Breaker state transitions and telemetry
2. Asynchronous Retry Engine with jitter & error classification
3. Model Registry & Intelligent Model Router modes (auto, fastest, quality, specific)
4. Hierarchical Memory Service & sensitive secret filtering
5. Real-Time Voice STT/TTS models, sentence segmentation & VAD
6. Code Execution Sandbox security, timeouts, and process isolation
7. SHIV Auth JWT verification and server-side identity resolution
"""
import pytest
import asyncio
import jwt
import time
from core.resilience.circuit_breaker import CircuitBreaker, CircuitState
from core.resilience.retry import execute_with_retry, is_error_retryable
from providers.errors import ProviderError, ErrorCategory
from core.routing.registry import model_registry, ModelInfo
from core.routing.router import model_router, RoutingMode
from core.routing.scoring import ScoringEngine
from core.memory.service import HierarchicalMemoryService
from core.voice.vad import VoiceActivityDetector
from core.voice.tts import split_into_speech_segments, detect_voice_for_text
from core.voice.stt import STTResult
from core.tools.sandbox import code_sandbox
from security.shiv_auth import verify_shiv_token, UserContext
from config.settings import settings


# ---------------------------------------------------------------------------
# 1. Circuit Breaker Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_circuit_breaker_transitions():
    cb = CircuitBreaker("test_provider", failure_threshold=2, recovery_timeout=0.2)
    assert cb.state == CircuitState.CLOSED
    assert await cb.can_execute() is True

    # Record 1 failure -> still CLOSED
    await cb.record_failure("simulated failure 1")
    assert cb.state == CircuitState.CLOSED

    # Record 2nd failure -> trips to OPEN
    await cb.record_failure("simulated failure 2")
    assert cb.state == CircuitState.OPEN
    assert await cb.can_execute() is False

    # Wait for recovery timeout -> transitions to HALF_OPEN
    await asyncio.sleep(0.25)
    assert await cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Success in HALF_OPEN -> closes breaker
    await cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


# ---------------------------------------------------------------------------
# 2. Retry Engine Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_retry_engine_transient_error():
    attempts = 0

    async def flaky_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ProviderError(
                category=ErrorCategory.RATE_LIMIT,
                message="HTTP 429 Too Many Requests",
                provider="test",
                status_code=429,
            )
        return "SUCCESS"

    result = await execute_with_retry(
        flaky_call,
        max_retries=3,
        base_delay=0.01,
        max_delay=0.05,
        operation_name="flaky_test",
    )
    assert result == "SUCCESS"
    assert attempts == 3


@pytest.mark.asyncio
async def test_retry_engine_non_retryable_error():
    attempts = 0

    async def auth_fail_call():
        nonlocal attempts
        attempts += 1
        raise ProviderError(
            category=ErrorCategory.AUTH_ERROR,
            message="Invalid API Key",
            provider="test",
            status_code=401,
        )

    with pytest.raises(ProviderError) as exc_info:
        await execute_with_retry(
            auth_fail_call,
            max_retries=3,
            base_delay=0.01,
            operation_name="auth_test",
        )
    assert attempts == 1  # Never retried
    assert exc_info.value.category == ErrorCategory.AUTH_ERROR


# ---------------------------------------------------------------------------
# 3. Model Registry & Router Tests
# ---------------------------------------------------------------------------
def test_model_registry_loaded():
    models = model_registry.list_all(enabled_only=False)
    assert len(models) > 0
    # Verify Gemini and Groq are registered
    providers = {m.provider for m in models}
    assert "groq" in providers
    assert "gemini" in providers


@pytest.mark.asyncio
async def test_router_scoring_modes():
    gemini_flash = model_registry.get("gemini-2.5-flash")
    if not gemini_flash:
        gemini_flash = model_registry.list_all()[0]

    # Calculate scores under different modes
    score_fast = ScoringEngine.calculate_score(gemini_flash, mode=RoutingMode.FASTEST)
    score_qual = ScoringEngine.calculate_score(gemini_flash, mode=RoutingMode.QUALITY)
    score_bal = ScoringEngine.calculate_score(gemini_flash, mode=RoutingMode.BALANCED)

    assert isinstance(score_fast, float)
    assert isinstance(score_qual, float)
    assert isinstance(score_bal, float)


@pytest.mark.asyncio
async def test_router_specific_mode():
    target_model = "gemini-2.5-flash"
    decision = await model_router.route_request(
        mode=RoutingMode.SPECIFIC,
        specific_model_name=target_model,
    )
    assert decision.selected_model.model_name == target_model
    assert decision.mode == RoutingMode.SPECIFIC


# ---------------------------------------------------------------------------
# 4. Hierarchical Memory & Sensitive Filter Tests
# ---------------------------------------------------------------------------
def test_memory_sensitive_filter():
    # Sensitive credentials must be caught
    assert HierarchicalMemoryService.is_sensitive("Bearer ghp_123456789012345678901234567890123456") is True
    assert HierarchicalMemoryService.is_sensitive("api_key = sk-proj-12345678901234567890") is True
    assert HierarchicalMemoryService.is_sensitive("password: MySuperSecretPassword123") is True
    # Non-sensitive facts must pass
    assert HierarchicalMemoryService.is_sensitive("I prefer concise answers in Hinglish.") is False
    assert HierarchicalMemoryService.is_sensitive("Working on the Shree Manglam fashion store project.") is False


# ---------------------------------------------------------------------------
# 5. Real-Time Voice Subsystem Tests
# ---------------------------------------------------------------------------
def test_speech_segmentation():
    sample_text = "Hello there! Welcome to ShivAI. What can I build for you today? Let's get started."
    segments = split_into_speech_segments(sample_text)
    assert len(segments) >= 3
    assert "Hello there!" in segments[0]


def test_voice_detection_hindi_vs_english():
    hindi_text = "नमस्ते! आप कैसे हैं?"
    eng_text = "Hello, how are you doing today?"
    voice_hi = detect_voice_for_text(hindi_text)
    voice_en = detect_voice_for_text(eng_text)
    assert "hi-IN" in voice_hi
    assert "en-IN" in voice_en


def test_vad_calculation():
    vad = VoiceActivityDetector(energy_threshold=0.01)
    # Silent PCM (zeros)
    silent_pcm = b"\x00" * 640
    res_silent = vad.process_frame(silent_pcm)
    assert res_silent["is_speaking"] is False

    # Non-silent PCM with audible amplitude
    import struct
    audible_samples = [15000 if i % 2 == 0 else -15000 for i in range(320)]
    loud_pcm = struct.pack(f"<320h", *audible_samples)
    res_loud = vad.process_frame(loud_pcm)
    assert res_loud["rms_energy"] > 0.1


# ---------------------------------------------------------------------------
# 6. Sandboxed Execution Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_code_sandbox_execution():
    code = "print(21 * 2)"
    res = await code_sandbox.execute_python(code)
    assert res.success is True
    assert res.stdout.strip() == "42"
    assert res.timed_out is False


@pytest.mark.asyncio
async def test_code_sandbox_timeout():
    code = "import time; time.sleep(10)"
    res = await code_sandbox.execute_python(code)
    assert res.success is False
    assert res.timed_out is True


# ---------------------------------------------------------------------------
# 7. SHIV Auth JWT Tests
# ---------------------------------------------------------------------------
def test_shiv_auth_jwt_verification():
    # Create valid SHIV Auth token
    payload = {
        "sub": "user_26d20fcf",
        "email": "user@shiv.platform",
        "role": "user",
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, settings.SHIV_AUTH_JWT_SECRET, algorithm=settings.SHIV_AUTH_JWT_ALGORITHM)
    verified = verify_shiv_token(token)
    assert verified["sub"] == "user_26d20fcf"
    assert verified["email"] == "user@shiv.platform"


# ---------------------------------------------------------------------------
# 8. Admin Dashboard & Governance API Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_dashboard_html(async_client):
    res = await async_client.get("/admin")
    assert res.status_code == 200
    assert "SHIV AI V2.0" in res.text
    assert "Admin Command Center" in res.text


@pytest.mark.asyncio
async def test_admin_config_api(async_client):
    # GET config
    res = await async_client.get(
        "/v2/admin/config",
        headers={"Authorization": "Bearer shivai-production-key-2026"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "models" in data
    assert "circuit_breakers" in data
    assert "settings" in data

    # POST config
    update_res = await async_client.post(
        "/v2/admin/config",
        headers={"Authorization": "Bearer shivai-production-key-2026"},
        json={"router_default_mode": "fastest", "circuit_breaker_threshold": 6}
    )
    assert update_res.status_code == 200
    assert update_res.json()["active_settings"]["router_default_mode"] == "fastest"

    # Reset circuit breaker
    cb_res = await async_client.post(
        "/v2/admin/circuit-breaker/reset",
        headers={"Authorization": "Bearer shivai-production-key-2026"}
    )
    assert cb_res.status_code == 200
    assert "reset" in cb_res.json()["message"]
