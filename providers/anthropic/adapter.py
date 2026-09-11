"""
Anthropic Claude Provider Adapter.
Implements Messages API format and native SSE streaming.
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


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: Optional[str] = None, timeout_seconds: float = 45.0):
        key = api_key or settings.ANTHROPIC_API_KEY
        super().__init__(provider_name="anthropic", api_key=key)
        self.base_url = "https://api.anthropic.com/v1"
        self.timeout_seconds = timeout_seconds

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _prepare_payload(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        options = options or {}
        system_content = None
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                # Anthropic takes system prompt as top-level string
                if system_content is None:
                    system_content = content
                else:
                    system_content += f"\n\n{content}"
            elif role in ("user", "assistant"):
                anthropic_messages.append({"role": role, "content": content})

        if not anthropic_messages:
            anthropic_messages.append({"role": "user", "content": "Hello"})

        payload: Dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": options.get("max_tokens", 4096),
            "stream": stream,
        }
        if system_content:
            payload["system"] = system_content
        if "temperature" in options:
            payload["temperature"] = options["temperature"]

        return payload

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
                    message=f"Anthropic authentication failed: {status}",
                    provider="anthropic",
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            elif status == 429:
                if "credit" in body_lower or "quota" in body_lower or "balance" in body_lower:
                    return ProviderError(
                        category=ErrorCategory.QUOTA_EXCEEDED,
                        message="Anthropic credit or quota exhausted",
                        provider="anthropic",
                        model=model,
                        status_code=status,
                        raw_error=error_body,
                    )
                return ProviderError(
                    category=ErrorCategory.RATE_LIMIT,
                    message="Anthropic rate limit exceeded",
                    provider="anthropic",
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                    retry_after=retry_after,
                )
            elif status == 529:
                return ProviderError(
                    category=ErrorCategory.MODEL_UNAVAILABLE,
                    message="Anthropic API is currently overloaded",
                    provider="anthropic",
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            elif status in (408, 504):
                return ProviderError(
                    category=ErrorCategory.TIMEOUT,
                    message="Anthropic request timed out",
                    provider="anthropic",
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            elif status in (500, 502, 503):
                return ProviderError(
                    category=ErrorCategory.SERVER_ERROR,
                    message=f"Anthropic server error: {status}",
                    provider="anthropic",
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )
            else:
                return ProviderError(
                    category=ErrorCategory.BAD_REQUEST,
                    message=f"Anthropic request error ({status})",
                    provider="anthropic",
                    model=model,
                    status_code=status,
                    raw_error=error_body,
                )

        if isinstance(exception, (httpx.TimeoutException, TimeoutError)):
            return ProviderError(
                category=ErrorCategory.TIMEOUT,
                message="Timeout communicating with Anthropic API",
                provider="anthropic",
                model=model,
            )

        if isinstance(exception, httpx.RequestError):
            return ProviderError(
                category=ErrorCategory.NETWORK_ERROR,
                message=f"Network error communicating with Anthropic: {str(exception)}",
                provider="anthropic",
                model=model,
                raw_error=str(exception),
            )

        return ProviderError(
            category=ErrorCategory.UNKNOWN,
            message=f"Unexpected Anthropic error: {str(exception)}",
            provider="anthropic",
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
        url = f"{self.base_url}/messages"
        headers = self._get_headers()
        payload = self._prepare_payload(model, messages, options, stream=False)

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Extract text blocks
            content_blocks = data.get("content", [])
            text_pieces = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            content = "".join(text_pieces)
            finish_reason = data.get("stop_reason", "stop")

            usage_data = data.get("usage", {})
            usage = UsageInfo(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            )

            return UnifiedResponse(
                request_id=req_id,
                assistant="shivai",
                content=content,
                model=ModelIdentifier(provider="anthropic", model=model),
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
        url = f"{self.base_url}/messages"
        headers = self._get_headers()
        payload = self._prepare_payload(model, messages, options, stream=True)

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()

                    current_event = None
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("event: "):
                            current_event = line[7:].strip()
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            try:
                                data_obj = json.loads(data_str)
                                if current_event == "content_block_delta":
                                    delta_obj = data_obj.get("delta", {})
                                    if delta_obj.get("type") == "text_delta":
                                        yield UnifiedStreamChunk(
                                            request_id=req_id,
                                            assistant="shivai",
                                            delta=delta_obj.get("text", ""),
                                            model=ModelIdentifier(provider="anthropic", model=model),
                                        )
                                elif current_event == "message_delta":
                                    stop_reason = data_obj.get("delta", {}).get("stop_reason")
                                    if stop_reason:
                                        yield UnifiedStreamChunk(
                                            request_id=req_id,
                                            assistant="shivai",
                                            delta="",
                                            finish_reason=stop_reason,
                                            model=ModelIdentifier(provider="anthropic", model=model),
                                        )
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            raise self.normalize_error(e, model=model)

    async def health_check(self) -> Dict[str, Any]:
        if not self.is_configured:
            return {"provider": "anthropic", "status": "NOT_CONFIGURED", "available": False}
        return {"provider": "anthropic", "status": "HEALTHY", "available": True}
