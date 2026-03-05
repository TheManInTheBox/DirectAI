"""
Rate limiting middleware — tier-aware RPM + TPM enforcement.

Each API key (or client IP if unauthenticated) gets a pair of limiters:
  1. **RPM** — token-bucket capping requests per minute.
  2. **TPM** — sliding-window counter capping tokens per minute.

Tier limits (configured via ``TIER_LIMITS``):
  Open Source — 60 RPM,  100 000 TPM
  Managed    — 600 RPM, 1 000 000 TPM
  Enterprise — unlimited (placeholder, enforce at gateway)

When no tier can be resolved (auth disabled / env-var keys), the
**Open Source** tier limits are applied as a safe default.

Configuration via environment variables:
  DIRECTAI_RATE_LIMIT_RPM:         override Open Source RPM (default: 60)
  DIRECTAI_RATE_LIMIT_TPM:         override Open Source TPM (default: 100000)
  DIRECTAI_RATE_LIMIT_MAX_BUCKETS: max tracked keys before eviction (default: 50000)
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── Tier limit definitions ──────────────────────────────────────────


@dataclass(frozen=True)
class TierLimits:
    """Rate limits for a pricing tier."""

    rpm: int  # Requests per minute
    tpm: int  # Tokens per minute


TIER_LIMITS: dict[str, TierLimits] = {
    "open-source": TierLimits(rpm=60, tpm=100_000),
    "managed": TierLimits(rpm=600, tpm=1_000_000),
    "enterprise": TierLimits(rpm=10_000, tpm=100_000_000),  # effectively unlimited
    # Legacy aliases — map old DB values to new tiers during migration
    "developer": TierLimits(rpm=60, tpm=100_000),
    "pro": TierLimits(rpm=600, tpm=1_000_000),
}

DEFAULT_TIER = "open-source"

# Buckets older than this (seconds since last access) are eligible for eviction.
_BUCKET_TTL = 600  # 10 minutes
# Hard cap on tracked keys — prevents OOM even if all keys are "fresh".
_MAX_BUCKETS_DEFAULT = 50_000


# ── RPM limiter (token bucket) ──────────────────────────────────────


class _TokenBucket:
    """Token-bucket rate limiter for requests-per-minute.

    ``rate`` = tokens added per second = RPM / 60.
    ``burst`` = max tokens (allows short spikes above the steady rate).
    """

    __slots__ = ("rate", "burst", "tokens", "last_refill")

    def __init__(self, rpm: int) -> None:
        self.rate: float = rpm / 60.0  # tokens per second
        self.burst: int = max(5, rpm // 10)  # ~10-second burst window
        self.tokens: float = float(self.burst)
        self.last_refill: float = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


# ── TPM limiter (sliding window counter) ────────────────────────────


class _SlidingWindowCounter:
    """Sliding-window token counter for tokens-per-minute.

    Records token consumption in 1-second buckets. The window is 60
    seconds.  ``record(n)`` returns False if accepting *n* tokens would
    exceed the TPM limit.
    """

    __slots__ = ("limit", "_buckets", "_total")

    _WINDOW = 60  # seconds

    def __init__(self, tpm: int) -> None:
        self.limit = tpm
        # (timestamp_second, token_count) pairs — kept sorted by time.
        self._buckets: list[tuple[int, int]] = []
        self._total = 0

    def _prune(self, now_sec: int) -> None:
        cutoff = now_sec - self._WINDOW
        while self._buckets and self._buckets[0][0] <= cutoff:
            _, count = self._buckets.pop(0)
            self._total -= count

    def check(self, tokens: int = 0) -> bool:
        """Return True if *tokens* can be accepted within the window."""
        now_sec = int(time.monotonic())
        self._prune(now_sec)
        return (self._total + tokens) <= self.limit

    def record(self, tokens: int) -> bool:
        """Record *tokens*.  Returns True if within limit, False if over.

        If over the limit, the tokens are NOT recorded (caller should reject).
        """
        if tokens <= 0:
            return True
        now_sec = int(time.monotonic())
        self._prune(now_sec)
        if (self._total + tokens) > self.limit:
            return False
        # Append to current-second bucket
        if self._buckets and self._buckets[-1][0] == now_sec:
            ts, existing = self._buckets[-1]
            self._buckets[-1] = (ts, existing + tokens)
        else:
            self._buckets.append((now_sec, tokens))
        self._total += tokens
        return True

    @property
    def remaining(self) -> int:
        now_sec = int(time.monotonic())
        self._prune(now_sec)
        return max(0, self.limit - self._total)


# ── Combined per-key state ──────────────────────────────────────────


@dataclass
class _KeyState:
    """Per-key rate limit state — RPM bucket + TPM window."""

    rpm_bucket: _TokenBucket
    tpm_window: _SlidingWindowCounter
    tier: str
    last_access: float = field(default_factory=time.monotonic)

    @classmethod
    def for_tier(cls, tier: str) -> "_KeyState":
        limits = TIER_LIMITS.get(tier, TIER_LIMITS[DEFAULT_TIER])
        return cls(
            rpm_bucket=_TokenBucket(rpm=limits.rpm),
            tpm_window=_SlidingWindowCounter(tpm=limits.tpm),
            tier=tier,
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Tier-aware per-key rate limiter (RPM + TPM) with TTL eviction.

    Exempt paths: /healthz, /readyz, /metrics (probes/monitoring).

    **Tier resolution:**  On each request, the middleware attempts to
    resolve the API key's tier via ``app.state.key_store``.  If the store
    is unavailable or returns nothing, Developer-tier limits apply.

    **TPM enforcement:** The middleware enforces TPM *pre-request* as a
    rough gate.  Route handlers call ``record_tokens()`` after they know
    the real token count, which updates the sliding window.

    Eviction strategy (two-pronged, no background task):
      1. **TTL sweep** — every 1000 requests, evict keys not accessed
         in the last ``_BUCKET_TTL`` seconds.
      2. **Hard cap** — if len(keys) exceeds ``max_buckets`` after a
         new insert, evict the LRU entry (OrderedDict).
    """

    _EXEMPT_PATHS = {"/healthz", "/readyz", "/metrics"}
    _SWEEP_INTERVAL = 1000  # requests between TTL sweeps

    def __init__(  # noqa: ANN001
        self,
        app,
        rpm: int = 60,
        tpm: int = 100_000,
        max_buckets: int = _MAX_BUCKETS_DEFAULT,
    ) -> None:
        super().__init__(app)
        self._default_rpm = rpm
        self._default_tpm = tpm
        self._max_buckets = max_buckets
        # OrderedDict gives O(1) move-to-end (LRU) + insertion-order iteration.
        self._keys: OrderedDict[str, _KeyState] = OrderedDict()
        self._request_count = 0

    # ── Key state management ────────────────────────────────────

    def _get_or_create(self, key: str, tier: str) -> _KeyState:
        """Return the state for *key*, creating or upgrading if needed."""
        try:
            state = self._keys[key]
            self._keys.move_to_end(key)
            state.last_access = time.monotonic()
            # If tier changed (e.g. user upgraded), rebuild limiters
            if state.tier != tier:
                state = _KeyState.for_tier(tier)
                self._keys[key] = state
            return state
        except KeyError:
            state = _KeyState.for_tier(tier)
            self._keys[key] = state
            # Hard cap — evict LRU entry if over limit
            if len(self._keys) > self._max_buckets:
                self._keys.popitem(last=False)
            return state

    def _maybe_sweep(self) -> None:
        """Periodic TTL sweep — evict stale keys."""
        self._request_count += 1
        if self._request_count < self._SWEEP_INTERVAL:
            return
        self._request_count = 0

        cutoff = time.monotonic() - _BUCKET_TTL
        stale_keys = []
        for key, state in self._keys.items():
            if state.last_access < cutoff:
                stale_keys.append(key)
            else:
                break  # OrderedDict is sorted by last access
        for key in stale_keys:
            del self._keys[key]

    # ── Tier resolution ─────────────────────────────────────────

    async def _resolve_tier(self, request: Request, raw_key: str) -> str:
        """Resolve the user's pricing tier from the key store.

        Returns the tier string ('developer', 'pro', 'enterprise') or
        DEFAULT_TIER if resolution fails or is unavailable.
        """
        key_store = getattr(request.app.state, "key_store", None)
        if key_store is None or not key_store.enabled:
            return DEFAULT_TIER
        try:
            info = await key_store.validate(raw_key)
            if info is not None:
                # Stash key_info early so auth dependency can skip re-validation
                request.state.key_info = info
                return info.tier
        except Exception:
            logger.debug("Tier lookup failed for key — using default", exc_info=True)
        return DEFAULT_TIER

    # ── Dispatch ────────────────────────────────────────────────

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self._EXEMPT_PATHS:
            return await call_next(request)

        self._maybe_sweep()

        # Extract key identifier
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            raw_key = auth_header[7:].strip()
            bucket_key = raw_key[:64]  # cap length for dict key
        else:
            raw_key = ""
            bucket_key = request.client.host if request.client else "unknown"

        # Resolve tier (hits key_store cache, not a raw DB query each time)
        tier = await self._resolve_tier(request, raw_key) if raw_key else DEFAULT_TIER

        state = self._get_or_create(bucket_key, tier)
        limits = TIER_LIMITS.get(tier, TIER_LIMITS[DEFAULT_TIER])

        # ── RPM check ──────────────────────────────────────────
        if not state.rpm_bucket.allow():
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": "Rate limit exceeded. You are sending requests too quickly.",
                        "type": "rate_limit_error",
                        "code": "rate_limit_exceeded",
                    }
                },
                headers={
                    "Retry-After": "1",
                    "X-RateLimit-Limit-Requests": str(limits.rpm),
                    "X-RateLimit-Limit-Tokens": str(limits.tpm),
                    "X-RateLimit-Remaining-Requests": "0",
                },
            )

        # ── TPM pre-check (rough — route handler records actuals) ─
        if not state.tpm_window.check():
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": "Token rate limit exceeded. You have consumed too many tokens this minute.",
                        "type": "rate_limit_error",
                        "code": "token_rate_limit_exceeded",
                    }
                },
                headers={
                    "Retry-After": "5",
                    "X-RateLimit-Limit-Requests": str(limits.rpm),
                    "X-RateLimit-Limit-Tokens": str(limits.tpm),
                    "X-RateLimit-Remaining-Tokens": "0",
                },
            )

        # ── Monthly credit cap (Developer tier only) ────────────
        if tier == DEFAULT_TIER and raw_key:
            key_info = getattr(request.state, "key_info", None)
            if key_info is not None:
                key_store = getattr(request.app.state, "key_store", None)
                if key_store is not None and key_store.enabled:
                    settings = get_settings()
                    cap_cents = settings.developer_monthly_credit_cents
                    try:
                        spend_cents = await key_store.get_monthly_spend(key_info.user_id)
                        if spend_cents >= cap_cents:
                            return JSONResponse(
                                status_code=429,
                                content={
                                    "error": {
                                        "message": (
                                            f"Monthly credit limit exceeded. "
                                            f"Open Source tier includes ${cap_cents / 100:.2f}/month in credits. "
                                            f"Current spend: ${spend_cents / 100:.2f}. "
                                            f"Upgrade to Managed for higher limits."
                                        ),
                                        "type": "spending_limit_error",
                                        "code": "monthly_credit_exceeded",
                                    }
                                },
                                headers={
                                    "Retry-After": "3600",
                                },
                            )
                    except Exception:
                        logger.debug("Spend check failed — allowing request", exc_info=True)

        # Stash state on request so route handlers can record tokens
        request.state.rate_limit_state = state

        response = await call_next(request)

        # Add rate limit headers to successful responses
        response.headers["X-RateLimit-Limit-Requests"] = str(limits.rpm)
        response.headers["X-RateLimit-Limit-Tokens"] = str(limits.tpm)
        response.headers["X-RateLimit-Remaining-Tokens"] = str(state.tpm_window.remaining)

        return response


def record_tokens(request: Request, tokens: int) -> bool:
    """Record token consumption against the rate limiter.

    Call this from route handlers after you know the actual token count.
    Returns False if recording would exceed the TPM limit (request already
    in-flight, so this is informational — the *next* request will be rejected).
    """
    state: Optional[_KeyState] = getattr(request.state, "rate_limit_state", None)
    if state is None:
        return True
    return state.tpm_window.record(tokens)
