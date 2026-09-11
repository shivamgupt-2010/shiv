"""
Sliding-window In-Memory Rate Limiter for API Gateway.
"""
import time
from collections import defaultdict
from typing import Dict, List
from fastapi import Request, HTTPException, status
from config.settings import settings


class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60.0
        self._history: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        now = time.time()
        window_start = now - self.window_seconds

        # Prune older records
        records = [t for t in self._history[client_id] if t > window_start]
        self._history[client_id] = records

        if len(records) >= self.requests_per_minute:
            oldest = records[0]
            retry_after = int(self.window_seconds - (now - oldest)) + 1
            return False, max(1, retry_after)

        self._history[client_id].append(now)
        return True, 0


rate_limiter = SlidingWindowRateLimiter(requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)


async def rate_limit_middleware_check(request: Request) -> None:
    """Dependency that applies rate limits to incoming requests."""
    # Whitelist local health checks
    if request.url.path in ("/api/v1/health", "/docs", "/openapi.json"):
        return

    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = rate_limiter.is_allowed(client_ip)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Client request rate limit exceeded. Retry in {retry_after} seconds.",
                    "retry_after": retry_after,
                }
            },
            headers={"Retry-After": str(retry_after)},
        )
