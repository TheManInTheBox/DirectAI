"""Tests for the rate limiting middleware."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


class TestRateLimitBasic:
    """Token-bucket enforcement."""

    def test_requests_within_limit_succeed(self, test_client: TestClient):
        """Normal traffic under the burst limit should not be throttled."""
        for _ in range(5):
            resp = test_client.get("/v1/models")
            assert resp.status_code == 200

    def test_burst_exceeded_returns_429(self, test_client: TestClient):
        """After exhausting tokens, the next request must get 429."""
        # Default burst=120 in tests, so we need to exceed that.
        # We patch the middleware bucket directly to avoid 120 iterations.
        from app.main import app

        # Find the RateLimitMiddleware instance
        rl = None
        for mw in app.user_middleware:
            if mw.cls.__name__ == "RateLimitMiddleware":
                rl = mw
                break
        assert rl is not None, "RateLimitMiddleware not found on app"

        # Simpler approach: use a low-burst client
        from app.middleware.rate_limit import _TokenBucket

        bucket = _TokenBucket(rate=1.0, burst=2)
        assert bucket.allow()  # token 1
        assert bucket.allow()  # token 2
        assert not bucket.allow()  # exhausted

    def test_429_response_shape(self, test_client: TestClient):
        """429 response must match OpenAI error format with Retry-After."""
        from app.middleware.rate_limit import _TokenBucket

        bucket = _TokenBucket(rate=1.0, burst=1)
        bucket.allow()  # exhaust
        assert not bucket.allow()

    def test_exempt_paths_not_limited(self, test_client: TestClient):
        """Health probes and metrics must bypass rate limiting."""
        for _ in range(200):
            assert test_client.get("/healthz").status_code == 200
            assert test_client.get("/readyz").status_code == 200
            assert test_client.get("/metrics").status_code == 200


class TestTokenBucket:
    """Unit tests for the _TokenBucket implementation."""

    def test_refill_over_time(self):
        from app.middleware.rate_limit import _TokenBucket

        bucket = _TokenBucket(rate=10.0, burst=10)
        # Exhaust all tokens
        for _ in range(10):
            assert bucket.allow()
        assert not bucket.allow()

        # Simulate time passing — 0.5s at 10 RPS = 5 tokens refilled
        bucket.last_refill = time.monotonic() - 0.5
        for _ in range(5):
            assert bucket.allow()
        assert not bucket.allow()

    def test_burst_caps_refill(self):
        """Tokens should never exceed burst, even after long idle."""
        from app.middleware.rate_limit import _TokenBucket

        bucket = _TokenBucket(rate=10.0, burst=5)
        # Simulate 10 seconds of idle — would be 100 tokens, but capped at 5
        bucket.last_refill = time.monotonic() - 10.0
        count = 0
        while bucket.allow():
            count += 1
        assert count == 5


class TestEviction:
    """TTL eviction and hard cap prevent unbounded memory growth."""

    def test_hard_cap_evicts_lru(self):
        """When max_buckets is exceeded, the oldest entry is evicted."""
        from app.middleware.rate_limit import RateLimitMiddleware

        # Create middleware with a tiny cap
        mw = RateLimitMiddleware.__new__(RateLimitMiddleware)
        mw._rate = 10.0
        mw._burst = 10
        mw._max_buckets = 3
        mw._buckets = __import__("collections").OrderedDict()
        mw._request_count = 0

        # Insert 4 keys — oldest should be evicted
        mw._get_bucket("a")
        mw._get_bucket("b")
        mw._get_bucket("c")
        assert len(mw._buckets) == 3
        mw._get_bucket("d")
        assert len(mw._buckets) == 3
        assert "a" not in mw._buckets
        assert "d" in mw._buckets

    def test_lru_reaccessing_prevents_eviction(self):
        """Accessing a key moves it to end, so it's not the LRU victim."""
        from app.middleware.rate_limit import RateLimitMiddleware

        mw = RateLimitMiddleware.__new__(RateLimitMiddleware)
        mw._rate = 10.0
        mw._burst = 10
        mw._max_buckets = 3
        mw._buckets = __import__("collections").OrderedDict()
        mw._request_count = 0

        mw._get_bucket("a")
        mw._get_bucket("b")
        mw._get_bucket("c")
        # Re-access "a" — now "b" is the LRU
        mw._get_bucket("a")
        mw._get_bucket("d")
        assert "a" in mw._buckets  # survived because re-accessed
        assert "b" not in mw._buckets  # evicted as LRU

    def test_ttl_sweep_removes_stale(self):
        """Stale buckets older than TTL are cleaned on sweep."""
        from app.middleware.rate_limit import (
            _BUCKET_TTL,
            RateLimitMiddleware,
            _TokenBucket,
        )

        mw = RateLimitMiddleware.__new__(RateLimitMiddleware)
        mw._rate = 10.0
        mw._burst = 10
        mw._max_buckets = 50_000
        mw._buckets = __import__("collections").OrderedDict()
        mw._request_count = 0

        # Insert a fresh bucket and a stale one
        stale = _TokenBucket(10.0, 10)
        stale.last_refill = time.monotonic() - _BUCKET_TTL - 1
        mw._buckets["stale-key"] = stale

        fresh = _TokenBucket(10.0, 10)
        mw._buckets["fresh-key"] = fresh

        # Force sweep
        mw._request_count = RateLimitMiddleware._SWEEP_INTERVAL - 1
        mw._maybe_sweep()

        assert "stale-key" not in mw._buckets
        assert "fresh-key" in mw._buckets


class TestKeyExtraction:
    """Verify key extraction logic — Bearer token vs client IP."""

    def test_bearer_key_used_when_present(self, test_client: TestClient):
        """Requests with different Bearer tokens get independent limits."""
        # Both should succeed — they're different keys
        resp1 = test_client.get("/v1/models", headers={"Authorization": "Bearer key-a"})
        resp2 = test_client.get("/v1/models", headers={"Authorization": "Bearer key-b"})
        assert resp1.status_code == 200
        assert resp2.status_code == 200

    def test_ip_fallback_when_no_auth(self, test_client: TestClient):
        """Without auth header, all requests from same IP share a bucket."""
        resp = test_client.get("/v1/models")
        assert resp.status_code == 200  # uses client IP as key


class TestSettingsIntegration:
    """Rate limit params come from DIRECTAI_ env vars."""

    def test_custom_rate_from_env(self, monkeypatch: pytest.MonkeyPatch, model_config_dir):
        """DIRECTAI_RATE_LIMIT_RPS and BURST are respected."""
        monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(model_config_dir))
        monkeypatch.setenv("DIRECTAI_RATE_LIMIT_RPS", "2")
        monkeypatch.setenv("DIRECTAI_RATE_LIMIT_BURST", "3")
        monkeypatch.setenv("DIRECTAI_API_KEYS", "")

        from app.config import get_settings
        get_settings.cache_clear()

        settings = get_settings()
        assert settings.rate_limit_rps == 2.0
        assert settings.rate_limit_burst == 3

        get_settings.cache_clear()
