"""
Google Gemini Provider Adapter.
Implements Google AI generateContent & streamGenerateContent REST APIs with x-goog-api-key header.
"""
import json
import time
import httpx
from typing import List, Dict, Any, Optional, AsyncIterator
from config.settings import settings
from providers.base import (
    AIProvider,
    UnifiedResponse,
    UnifiedStreamChunk,
    ModelIdentifier,
    UsageInfo,
)
from providers.errors import ProviderError, ErrorCategory


class GeminiProvider(AIProvider):
    def __init__(self, api_key: Optional[str] = None, timeout_seconds: float = 45.0):
        key = api_key or settings.GEMINI_API_KEY
        super().__init__(provider_name="gemini", api_key=key)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.timeout_seconds = timeout_seconds

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["x-goog-api-key"] = self.api_key
        return headers

    def _prepare_payload(
        self,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        options = options or {}
        system_text = None
        contents = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                if system_text is None:
                    system_text = content
                else:
                    system_text += f"\n\n{content}"
            elif role in ("user", "assistant"):
                gemini_role = "user" if role == "user" else "model"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}],
                })

        if not contents:
            contents.append({"role": "user", "parts": [{"text": "Hello"}]})

        payload: Dict[str, Any] = {
            "contents": contents,
        }
        if system_text:
            payload["systemInstruction"] = {
                "parts": [{"text": system_text}]
            }

        generation_config: Dict[str, Any] = {}
        if "temperature" in options:
            generation_config["temperature"] = options["temperature"]
        if "max_tokens" in options:
            generation_config["maxOutputTokens"] = options["max_tokens"]
        if generation_config:
            payload["generationConfig"] = generation_config

        return payload

    def normalize_error(self, exception: Exception, model: Optional[str] = None) -> ProviderError:
        if isinstance(exception, ProviderError):
            return exception

        if isinstance(exception, httpx.HTTPStatusError):
            status = exception.response.status_code
            error_body = ""
            try:
                error_body = exception.response.text
            except Exception:
                pass

            body_lower = error_body.lower()

            if status in (401, 403) or "api_key_invalid" in body_lower or "unauthenticated" in body_lower:
                return ProviderError(
                    category=ErrorCategory.AUTH_ERROR,
                    message=f"Gemini authentication error: {status}",
                    provider="gemini",
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            elif status == 429 or "resource_exhausted" in body_lower:
                if "quota" in body_lower or "exhausted" in body_lower:
                    return ProviderError(
                        category=ErrorCategory.QUOTA_EXCEEDED,
                        message="Gemini quota or resource exhausted",
                        provider="gemini",
                        model=model,
                        status_code=status,
                        raw_error=error_body,
                    )
                return ProviderError(
                    category=ErrorCategory.RATE_LIMIT,
                    message="Gemini rate limit exceeded",
                    provider="gemini",
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            elif status == 503 or "unavailable" in body_lower:
                return ProviderError(
                    category=ErrorCategory.MODEL_UNAVAILABLE,
                    message="Gemini service temporarily unavailable",
                    provider="gemini",
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            elif status in (408, 504):
                return ProviderError(
                    category=ErrorCategory.TIMEOUT,
                    message="Gemini request timed out",
                    provider="gemini",
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            elif status >= 500:
                return ProviderError(
                    category=ErrorCategory.SERVER_ERROR,
                    message=f"Gemini server error ({status})",
                    provider="gemini",
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            else:
                return ProviderError(
                    category=ErrorCategory.BAD_REQUEST,
                    message=f"Gemini bad request ({status})",
                    provider="gemini",
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )

        if isinstance(exception, (httpx.TimeoutException, TimeoutError)):
            return ProviderError(
                category=ErrorCategory.TIMEOUT,
                message="Timeout communicating with Gemini API",
                provider="gemini",
                model=model,
            )

        if isinstance(exception, httpx.RequestError):
            return ProviderError(
                category=ErrorCategory.NETWORK_ERROR,
                message=f"Network error communicating with Gemini: {str(exception)}",
                provider="gemini",
                model=model,
                raw_error=str(exception),
            )

        return ProviderError(
            category=ErrorCategory.UNKNOWN,
            message=f"Unexpected Gemini error: {str(exception)}",
            provider="gemini",
            model=model,
            raw_error=str(exception),
        )

    async def generate(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> UnifiedResponse:
        req_id = request_id or "req-default"
        url = f"{self.base_url}/{model}:generateContent"
        headers = self._get_headers()
        payload = self._prepare_payload(messages, options)

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            candidates = data.get("candidates", [])
            content = ""
            finish_reason = "stop"
            if candidates:
                first_cand = candidates[0]
                parts = first_cand.get("content", {}).get("parts", [])
                content = "".join([p.get("text", "") for p in parts if "text" in p])
                finish_reason = first_cand.get("finishReason", "stop").lower()

            usage_meta = data.get("usageMetadata", {})
            usage = UsageInfo(
                input_tokens=usage_meta.get("promptTokenCount", 0),
                output_tokens=usage_meta.get("candidatesTokenCount", 0),
                total_tokens=usage_meta.get("totalTokenCount", 0),
            )

            return UnifiedResponse(
                request_id=req_id,
                assistant="shivai",
                content=content,
                model=ModelIdentifier(provider="gemini", model=model),
                usage=usage,
                finish_reason=finish_reason,
                latency_ms=latency_ms,
            )
        except Exception as e:
            raise self.normalize_error(e, model=model)

    async def stream(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> AsyncIterator[UnifiedStreamChunk]:
        req_id = request_id or "req-default"
        url = f"{self.base_url}/{model}:streamGenerateContent?alt=sse"
        headers = self._get_headers()
        payload = self._prepare_payload(messages, options)

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        try:
                            chunk_data = json.loads(data_str)
                            candidates = chunk_data.get("candidates", [])
                            if not candidates:
                                continue
                            parts = candidates[0].get("content", {}).get("parts", [])
                            text = "".join([p.get("text", "") for p in parts if "text" in p])
                            finish = candidates[0].get("finishReason")
                            if text or finish:
                                yield UnifiedStreamChunk(
                                    request_id=req_id,
                                    assistant="shivai",
                                    delta=text,
                                    finish_reason=finish.lower() if finish else None,
                                    model=ModelIdentifier(provider="gemini", model=model),
                                )
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            raise self.normalize_error(e, model=model)

    async def health_check(self) -> Dict[str, Any]:
        if not self.is_configured:
            return {"provider": "gemini", "status": "NOT_CONFIGURED", "available": False}
        return {"provider": "gemini", "status": "HEALTHY", "available": True}
