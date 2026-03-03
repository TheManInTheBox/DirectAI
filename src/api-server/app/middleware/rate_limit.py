"""
Rate limiting middleware — token-bucket per API key.

Provides per-key request rate limiting for the API server.
When no API key is present (dev mode, auth disabled), uses client IP.

Configuration via environment variables:
  DIRECTAI_RATE_LIMIT_RPS:   requests per second per key (default: 60)
  DIRECTAI_RATE_LIMIT_BURST: maximum burst size (default: 120)
  DIRECTAI_RATE_LIMIT_MAX_BUCKETS: max tracked keys before eviction (default: 50000)
"""

from __future__ import annotations

import time
from collections import OrderedDict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Buckets older than this (seconds since last access) are eligible for eviction.
_BUCKET_TTL = 600  # 10 minutes
# Hard cap on tracked keys — prevents OOM even if all keys are "fresh".
_MAX_BUCKETS_DEFAULT = 50_000


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
    """Per-key token-bucket rate limiter with TTL eviction.

    Exempt paths: /healthz, /readyz, /metrics (probes/monitoring).

    Eviction strategy (two-pronged, no background task):
      1. **TTL sweep** — every 1000 requests, evict buckets not accessed
         in the last ``_BUCKET_TTL`` seconds.  O(n) but infrequent.
      2. **Hard cap** — if len(buckets) exceeds ``max_buckets`` after a
         new insert, evict the oldest entry (LRU via OrderedDict).
         This bounds memory even under a DDoS with unique keys.
    """

    _EXEMPT_PATHS = {"/healthz", "/readyz", "/metrics"}
    _SWEEP_INTERVAL = 1000  # requests between TTL sweeps

    def __init__(  # noqa: ANN001
        self,
        app,
        rate: float = 60.0,
        burst: int = 120,
        max_buckets: int = _MAX_BUCKETS_DEFAULT,
    ) -> None:
        super().__init__(app)
        self._rate = rate
        self._burst = burst
        self._max_buckets = max_buckets
        # OrderedDict gives O(1) move-to-end (LRU) + insertion-order iteration.
        self._buckets: OrderedDict[str, _TokenBucket] = OrderedDict()
        self._request_count = 0

    def _get_bucket(self, key: str) -> _TokenBucket:
        """Return the bucket for *key*, creating it if needed.

        Newly accessed buckets are moved to the end (most-recently-used).
        """
        try:
            bucket = self._buckets[key]
            self._buckets.move_to_end(key)
            return bucket
        except KeyError:
            bucket = _TokenBucket(self._rate, self._burst)
            self._buckets[key] = bucket
            # Hard cap — evict LRU entry if over limit
            if len(self._buckets) > self._max_buckets:
                self._buckets.popitem(last=False)
            return bucket

    def _maybe_sweep(self) -> None:
        """Periodic TTL sweep — evict stale buckets."""
        self._request_count += 1
        if self._request_count < self._SWEEP_INTERVAL:
            return
        self._request_count = 0

        cutoff = time.monotonic() - _BUCKET_TTL
        # Iterate oldest-first; stop early because OrderedDict is sorted by
        # last access (move_to_end on every hit).
        stale_keys = []
        for key, bucket in self._buckets.items():
            if bucket.last_refill < cutoff:
                stale_keys.append(key)
            else:
                # Everything after this is newer — stop scanning.
                break
        for key in stale_keys:
            del self._buckets[key]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self._EXEMPT_PATHS:
            return await call_next(request)

        self._maybe_sweep()

        # Key by API key if present, otherwise by client IP
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            key = auth_header[7:].strip()[:64]  # cap key length
        else:
            key = request.client.host if request.client else "unknown"

        bucket = self._get_bucket(key)
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
