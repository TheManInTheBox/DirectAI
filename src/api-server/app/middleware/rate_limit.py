"""
Rate limiting middleware — token-bucket per API key.

Provides per-key request rate limiting for the API server.
When no API key is present (dev mode, auth disabled), uses client IP.

Configuration via environment variables:
  DIRECTAI_RATE_LIMIT_RPS:   requests per second per key (default: 60)
  DIRECTAI_RATE_LIMIT_BURST: maximum burst size (default: 120)
"""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class _TokenBucket:
    """Simple token-bucket rate limiter."""

    __slots__ = ("rate", "burst", "tokens", "last_refill")

    def __init__(self, rate: float, burst: int) -> None:
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_refill = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-key token-bucket rate limiter.

    Exempt paths: /healthz, /readyz, /metrics (probes/monitoring).
    """

    _EXEMPT_PATHS = {"/healthz", "/readyz", "/metrics"}

    def __init__(self, app, rate: float = 60.0, burst: int = 120) -> None:  # noqa: ANN001
        super().__init__(app)
        self._rate = rate
        self._burst = burst
        self._buckets: dict[str, _TokenBucket] = defaultdict(
            lambda: _TokenBucket(self._rate, self._burst)
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self._EXEMPT_PATHS:
            return await call_next(request)

        # Key by API key if present, otherwise by client IP
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            key = auth_header[7:].strip()[:64]  # cap key length
        else:
            key = request.client.host if request.client else "unknown"

        bucket = self._buckets[key]
        if not bucket.allow():
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": "Rate limit exceeded. Please slow down.",
                        "type": "rate_limit_error",
                        "code": "rate_limit_exceeded",
                    }
                },
                headers={
                    "Retry-After": str(int(1.0 / self._rate) + 1),
                    "X-RateLimit-Limit": str(self._burst),
                },
            )

        return await call_next(request)
