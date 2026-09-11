"""
Base adapter for OpenAI-compatible endpoints (OpenAI, Groq, DeepSeek, Mistral, Generic).
"""
import json
import time
import httpx
from typing import List, Dict, Any, Optional, AsyncIterator
from providers.base import (
    AIProvider,
    UnifiedResponse,
    UnifiedStreamChunk,
    ModelIdentifier,
    UsageInfo,
)
from providers.errors import ProviderError, ErrorCategory


class BaseOpenAICompatibleProvider(AIProvider):
    """Handles chat completions and SSE streaming for OpenAI-compliant endpoints."""

    def __init__(
        self,
        provider_name: str,
        api_key: Optional[str],
        base_url: str,
        default_headers: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 45.0,
    ):
        super().__init__(provider_name=provider_name, api_key=api_key)
        self.base_url = base_url.rstrip("/")
        self.default_headers = default_headers or {}
        self.timeout_seconds = timeout_seconds

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            **self.default_headers,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def normalize_error(self, exception: Exception, model: Optional[str] = None) -> ProviderError:
        if isinstance(exception, ProviderError):
            return exception

        if isinstance(exception, httpx.HTTPStatusError):
            status = exception.response.status_code
            error_body = ""
            retry_after = None

            try:
                error_body = exception.response.text
                retry_header = exception.response.headers.get("retry-after")
                if retry_header and retry_header.isdigit():
                    retry_after = int(retry_header)
            except Exception:
                pass

            body_lower = error_body.lower()

            if status in (401, 403):
                return ProviderError(
                    category=ErrorCategory.AUTH_ERROR,
                    message=f"Authentication failed for {self.provider_name}: {status}",
                    provider=self.provider_name,
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            elif status == 429:
                if any(kw in body_lower for kw in ["quota", "insufficient", "credit", "billing", "exceeded your current quota"]):
                    return ProviderError(
                        category=ErrorCategory.QUOTA_EXCEEDED,
                        message=f"Quota exhausted for {self.provider_name}",
                        provider=self.provider_name,
                        model=model,
                        status_code=status,
                        raw_error=error_body,
                    )
                return ProviderError(
                    category=ErrorCategory.RATE_LIMIT,
                    message=f"Rate limit exceeded for {self.provider_name}",
                    provider=self.provider_name,
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                    retry_after=retry_after,
                )
            elif status in (408, 504):
                return ProviderError(
                    category=ErrorCategory.TIMEOUT,
                    message=f"Request to {self.provider_name} timed out: {status}",
                    provider=self.provider_name,
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            elif status == 400 and ("context" in body_lower or "token" in body_lower or "length" in body_lower):
                return ProviderError(
                    category=ErrorCategory.CONTEXT_TOO_LARGE,
                    message=f"Context window exceeded for {self.provider_name}",
                    provider=self.provider_name,
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            elif status in (500, 502, 503):
                return ProviderError(
                    category=ErrorCategory.SERVER_ERROR,
                    message=f"Server error from {self.provider_name}: {status}",
                    provider=self.provider_name,
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            else:
                return ProviderError(
                    category=ErrorCategory.BAD_REQUEST if status < 500 else ErrorCategory.SERVER_ERROR,
                    message=f"Error from {self.provider_name} (HTTP {status})",
                    provider=self.provider_name,
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )

        if isinstance(exception, (httpx.TimeoutException, TimeoutError)):
            return ProviderError(
                category=ErrorCategory.TIMEOUT,
                message=f"Connection timeout to {self.provider_name}",
                provider=self.provider_name,
                model=model,
            )

        if isinstance(exception, httpx.RequestError):
            return ProviderError(
                category=ErrorCategory.NETWORK_ERROR,
                message=f"Network communication failure to {self.provider_name}: {str(exception)}",
                provider=self.provider_name,
                model=model,
                raw_error=str(exception),
            )

        return ProviderError(
            category=ErrorCategory.UNKNOWN,
            message=f"Unexpected error with {self.provider_name}: {str(exception)}",
            provider=self.provider_name,
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
        url = f"{self.base_url}/chat/completions"
        headers = self._get_headers()
        options = options or {}

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if "temperature" in options:
            payload["temperature"] = options["temperature"]
        if "max_tokens" in options:
            payload["max_tokens"] = options["max_tokens"]

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            latency_ms = (time.perf_counter() - start_time) * 1000.0
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            finish_reason = choice.get("finish_reason", "stop")

            usage_data = data.get("usage", {})
            usage = UsageInfo(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

            return UnifiedResponse(
                request_id=req_id,
                assistant="shivai",
                content=content,
                model=ModelIdentifier(provider=self.provider_name, model=model),
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
        url = f"{self.base_url}/chat/completions"
        headers = self._get_headers()
        options = options or {}

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if "temperature" in options:
            payload["temperature"] = options["temperature"]
        if "max_tokens" in options:
            payload["max_tokens"] = options["max_tokens"]

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            chunk_json = json.loads(data_str)
                            choices = chunk_json.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            text = delta.get("content") or delta.get("reasoning_content") or ""
                            finish = choices[0].get("finish_reason")

                            if text or finish:
                                yield UnifiedStreamChunk(
                                    request_id=req_id,
                                    assistant="shivai",
                                    delta=text,
                                    finish_reason=finish,
                                    model=ModelIdentifier(provider=self.provider_name, model=model),
                                )
                        except json.JSONDecodeError:
                            continue
        except (GeneratorExit, asyncio.CancelledError):
            return
        except Exception as e:
            raise self.normalize_error(e, model=model)

    async def health_check(self) -> Dict[str, Any]:
        if not self.is_configured:
            return {"provider": self.provider_name, "status": "NOT_CONFIGURED", "available": False}
        return {"provider": self.provider_name, "status": "HEALTHY", "available": True}
