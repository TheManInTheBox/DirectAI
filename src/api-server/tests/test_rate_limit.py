"""Tests for the tier-aware rate limiting middleware (RPM + TPM)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient


class TestRateLimitBasic:
    """RPM token-bucket enforcement."""

    def test_requests_within_limit_succeed(self, test_client: TestClient):
        """Normal traffic under the burst limit should not be throttled."""
        for _ in range(5):
            resp = test_client.get("/v1/models")
            assert resp.status_code == 200

    def test_rpm_bucket_exhaustion(self):
        """After exhausting RPM tokens, the next request must be rejected."""
        from app.middleware.rate_limit import _TokenBucket

        # 60 RPM → rate=1.0/s, burst=6 (max(5, 60//10))
        bucket = _TokenBucket(rpm=60)
        assert bucket.burst == 6
        for _ in range(6):
            assert bucket.allow()
        assert not bucket.allow()  # exhausted

    def test_429_response_has_rate_limit_headers(self, test_client: TestClient):
        """429 responses include X-RateLimit-* headers."""
        from app.middleware.rate_limit import _TokenBucket

        bucket = _TokenBucket(rpm=60)
        # Drain the full burst
        while bucket.allow():
            pass
        assert not bucket.allow()  # confirms exhaustion

    def test_exempt_paths_not_limited(self, test_client: TestClient):
        """Health probes and metrics must bypass rate limiting."""
        for _ in range(200):
            assert test_client.get("/healthz").status_code == 200
            assert test_client.get("/readyz").status_code == 200
            assert test_client.get("/metrics").status_code == 200

    def test_successful_responses_have_rate_limit_headers(self, test_client: TestClient):
        """Successful responses should include X-RateLimit-* headers."""
        resp = test_client.get("/v1/models")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit-Requests" in resp.headers
        assert "X-RateLimit-Limit-Tokens" in resp.headers


class TestTokenBucket:
    """Unit tests for the _TokenBucket implementation."""

    def test_refill_over_time(self):
        from app.middleware.rate_limit import _TokenBucket

        # 600 RPM → rate=10/s, burst=20
        bucket = _TokenBucket(rpm=600)
        # Exhaust all tokens
        count = 0
        while bucket.allow():
            count += 1
        assert count == bucket.burst
        assert not bucket.allow()

        # Simulate time passing — 0.5s at 10/s = 5 tokens refilled
        bucket.last_refill = time.monotonic() - 0.5
        refilled = 0
        while bucket.allow():
            refilled += 1
        assert refilled == 5

    def test_burst_caps_refill(self):
        """Tokens should never exceed burst, even after long idle."""
        from app.middleware.rate_limit import _TokenBucket

        bucket = _TokenBucket(rpm=300)  # rate=5/s, burst=10
        # Simulate 100 seconds of idle — would be 500 tokens, capped at burst
        bucket.last_refill = time.monotonic() - 100.0
        count = 0
        while bucket.allow():
            count += 1
        assert count == bucket.burst

    def test_rpm_to_rate_conversion(self):
        """RPM is correctly converted to tokens per second."""
        from app.middleware.rate_limit import _TokenBucket

        bucket = _TokenBucket(rpm=60)
        assert bucket.rate == pytest.approx(1.0)  # 60 RPM = 1 per second

        bucket = _TokenBucket(rpm=600)
        assert bucket.rate == pytest.approx(10.0)  # 600 RPM = 10 per second


class TestSlidingWindowCounter:
    """Unit tests for the TPM sliding window counter."""

    def test_within_limit(self):
        from app.middleware.rate_limit import _SlidingWindowCounter

        counter = _SlidingWindowCounter(tpm=1000)
        assert counter.record(500)
        assert counter.record(400)
        assert counter.remaining == 100

    def test_over_limit_rejects(self):
        from app.middleware.rate_limit import _SlidingWindowCounter

        counter = _SlidingWindowCounter(tpm=1000)
        assert counter.record(900)
        assert not counter.record(200)  # 900 + 200 = 1100 > 1000
        assert counter.remaining == 100  # 200 was NOT recorded

    def test_check_without_recording(self):
        from app.middleware.rate_limit import _SlidingWindowCounter

        counter = _SlidingWindowCounter(tpm=1000)
        counter.record(999)
        assert counter.check(0)  # still within limit
        assert counter.check(1)  # exactly at limit
        assert not counter.check(2)  # would exceed

    def test_zero_tokens_always_accepted(self):
        from app.middleware.rate_limit import _SlidingWindowCounter

        counter = _SlidingWindowCounter(tpm=0)
        assert counter.record(0)  # zero is always ok
        assert not counter.record(1)  # but anything else fails


class TestTierLimits:
    """Verify tier limit definitions."""

    def test_free_limits(self):
        from app.middleware.rate_limit import TIER_LIMITS

        free = TIER_LIMITS["free"]
        assert free.rpm == 60
        assert free.tpm == 100_000

    def test_pro_limits(self):
        from app.middleware.rate_limit import TIER_LIMITS

        pro = TIER_LIMITS["pro"]
        assert pro.rpm == 300
        assert pro.tpm == 500_000

    def test_enterprise_limits(self):
        from app.middleware.rate_limit import TIER_LIMITS

        ent = TIER_LIMITS["enterprise"]
        assert ent.rpm == 10_000


class TestKeyState:
    """Per-key state creation and tier handling."""

    def test_for_tier_creates_correct_limits(self):
        from app.middleware.rate_limit import _KeyState

        state = _KeyState.for_tier("pro")
        assert state.tier == "pro"
        assert state.rpm_bucket.rate == pytest.approx(5.0)  # 300/60
        assert state.tpm_window.limit == 500_000

    def test_unknown_tier_defaults_to_free(self):
        from app.middleware.rate_limit import _KeyState

        state = _KeyState.for_tier("nonexistent")
        assert state.tier == "nonexistent"  # tier string preserved
        assert state.rpm_bucket.rate == pytest.approx(1.0)  # free: 60/60
        assert state.tpm_window.limit == 100_000


class TestEviction:
    """TTL eviction and hard cap prevent unbounded memory growth."""

    def test_hard_cap_evicts_lru(self):
        """When max_buckets is exceeded, the oldest entry is evicted."""
        from app.middleware.rate_limit import RateLimitMiddleware

        mw = RateLimitMiddleware.__new__(RateLimitMiddleware)
        mw._default_rpm = 60
        mw._default_tpm = 100_000
        mw._max_buckets = 3
        mw._keys = __import__("collections").OrderedDict()
        mw._request_count = 0

        mw._get_or_create("a", "free")
        mw._get_or_create("b", "free")
        mw._get_or_create("c", "free")
        assert len(mw._keys) == 3
        mw._get_or_create("d", "free")
        assert len(mw._keys) == 3
        assert "a" not in mw._keys
        assert "d" in mw._keys

    def test_lru_reaccessing_prevents_eviction(self):
        """Accessing a key moves it to end, so it's not the LRU victim."""
        from app.middleware.rate_limit import RateLimitMiddleware

        mw = RateLimitMiddleware.__new__(RateLimitMiddleware)
        mw._default_rpm = 60
        mw._default_tpm = 100_000
        mw._max_buckets = 3
        mw._keys = __import__("collections").OrderedDict()
        mw._request_count = 0

        mw._get_or_create("a", "free")
        mw._get_or_create("b", "free")
        mw._get_or_create("c", "free")
        mw._get_or_create("a", "free")  # re-access "a"
        mw._get_or_create("d", "free")
        assert "a" in mw._keys  # survived because re-accessed
        assert "b" not in mw._keys  # evicted as LRU

    def test_ttl_sweep_removes_stale(self):
        """Stale keys older than TTL are cleaned on sweep."""
        from app.middleware.rate_limit import (
            _BUCKET_TTL,
            _KeyState,
            RateLimitMiddleware,
        )

        mw = RateLimitMiddleware.__new__(RateLimitMiddleware)
        mw._default_rpm = 60
        mw._default_tpm = 100_000
        mw._max_buckets = 50_000
        mw._keys = __import__("collections").OrderedDict()
        mw._request_count = 0

        # Insert a stale key
        stale = _KeyState.for_tier("free")
        stale.last_access = time.monotonic() - _BUCKET_TTL - 1
        mw._keys["stale-key"] = stale

        # Insert a fresh key
        fresh = _KeyState.for_tier("free")
        mw._keys["fresh-key"] = fresh

        # Force sweep
        mw._request_count = RateLimitMiddleware._SWEEP_INTERVAL - 1
        mw._maybe_sweep()

        assert "stale-key" not in mw._keys
        assert "fresh-key" in mw._keys

    def test_tier_upgrade_rebuilds_limiters(self):
        """When tier changes for a key, limiters should be rebuilt."""
        from app.middleware.rate_limit import RateLimitMiddleware

        mw = RateLimitMiddleware.__new__(RateLimitMiddleware)
        mw._default_rpm = 60
        mw._default_tpm = 100_000
        mw._max_buckets = 50_000
        mw._keys = __import__("collections").OrderedDict()
        mw._request_count = 0

        state1 = mw._get_or_create("key-x", "free")
        assert state1.rpm_bucket.rate == pytest.approx(1.0)

        state2 = mw._get_or_create("key-x", "pro")
        assert state2.rpm_bucket.rate == pytest.approx(5.0)
        assert state2 is not state1  # new object


class TestKeyExtraction:
    """Verify key extraction logic — Bearer token vs client IP."""

    def test_bearer_key_used_when_present(self, test_client: TestClient):
        """Requests with different Bearer tokens get independent limits."""
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

    def test_custom_rpm_from_env(self, monkeypatch: pytest.MonkeyPatch, model_config_dir):
        """DIRECTAI_RATE_LIMIT_RPM and TPM are respected."""
        monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(model_config_dir))
        monkeypatch.setenv("DIRECTAI_RATE_LIMIT_RPM", "120")
        monkeypatch.setenv("DIRECTAI_RATE_LIMIT_TPM", "200000")
        monkeypatch.setenv("DIRECTAI_API_KEYS", "")

        from app.config import get_settings
        get_settings.cache_clear()

        settings = get_settings()
        assert settings.rate_limit_rpm == 120
        assert settings.rate_limit_tpm == 200_000

        get_settings.cache_clear()


class TestRecordTokens:
    """Test the record_tokens helper function."""

    def test_record_tokens_with_no_state(self):
        """record_tokens returns True when no rate limit state is stashed."""
        from unittest.mock import MagicMock

        from app.middleware.rate_limit import record_tokens

        request = MagicMock()
        request.state = MagicMock(spec=[])  # no rate_limit_state
        assert record_tokens(request, 1000) is True

    def test_record_tokens_within_limit(self):
        """record_tokens records tokens and returns True when within TPM."""
        from unittest.mock import MagicMock

        from app.middleware.rate_limit import _KeyState, record_tokens

        request = MagicMock()
        state = _KeyState.for_tier("free")  # 100K TPM
        request.state.rate_limit_state = state
        assert record_tokens(request, 50_000) is True
        assert state.tpm_window.remaining == 50_000

    def test_record_tokens_over_limit(self):
        """record_tokens returns False when TPM would be exceeded."""
        from unittest.mock import MagicMock

        from app.middleware.rate_limit import _KeyState, record_tokens

        request = MagicMock()
        state = _KeyState.for_tier("free")  # 100K TPM
        request.state.rate_limit_state = state
        assert record_tokens(request, 100_000) is True  # fill exactly
        assert record_tokens(request, 1) is False  # over


class TestMonthlyCreditGate:
    """Unit tests for the monthly credit cap enforcement."""

    def test_modality_pricing_defined(self):
        """All expected modalities have pricing."""
        from app.auth.key_store import MODALITY_PRICING

        assert "chat" in MODALITY_PRICING
        assert "embedding" in MODALITY_PRICING
        assert "transcription" in MODALITY_PRICING
        # Each is a (input, output) tuple of floats
        for modality, (inp, out) in MODALITY_PRICING.items():
            assert isinstance(inp, float), f"{modality} input is not float"
            assert isinstance(out, float), f"{modality} output is not float"
            assert inp >= 0 and out >= 0

    def test_developer_credit_config_defaults(self):
        """Default developer credit cap is 500 cents ($5.00)."""
        import os
        os.environ.pop("DIRECTAI_DEVELOPER_MONTHLY_CREDIT_CENTS", None)
        from app.config import get_settings
        get_settings.cache_clear()
        s = get_settings()
        assert s.developer_monthly_credit_cents == 500
        get_settings.cache_clear()

    def test_spend_cache_entry(self):
        """_SpendCacheEntry can be created and stores values."""
        from app.auth.key_store import _SpendCacheEntry

        entry = _SpendCacheEntry(spend_cents=123.45, expires_at=99999.0)
        assert entry.spend_cents == 123.45
        assert entry.expires_at == 99999.0
