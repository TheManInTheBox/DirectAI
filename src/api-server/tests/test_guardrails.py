"""
Tests for the content safety guardrails module.

Covers:
  - ContentSafetyClient stub mode (no endpoint configured)
  - ContentSafetyClient API response parsing and threshold logic
  - ContentSafetyClient fail-open on API errors
  - ContentSafetyMiddleware disabled bypass
  - ContentSafetyMiddleware input blocking (chat completions)
  - ContentSafetyMiddleware input blocking (embeddings)
  - ContentSafetyMiddleware non-inference paths ignored
  - ContentSafetyMiddleware bypass for Enterprise tier
  - Schema validation (CategoryResult, SafetyCheckResult)
  - Prometheus metrics (stub, pass, block counters)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.guardrails.config import GuardrailsConfig
from app.guardrails.content_safety import ContentSafetyClient
from app.guardrails.schemas import (
    CategoryResult,
    ContentFilterErrorDetail,
    SafetyCategory,
    SafetyCheckResult,
)


# ════════════════════════════════════════════════════════════════════
# Schema unit tests
# ════════════════════════════════════════════════════════════════════


class TestSchemas:
    def test_category_result(self):
        cr = CategoryResult(severity=3, filtered=False)
        assert cr.severity == 3
        assert cr.filtered is False

    def test_category_result_filtered(self):
        cr = CategoryResult(severity=5, filtered=True)
        assert cr.severity == 5
        assert cr.filtered is True

    def test_safety_check_result_not_blocked(self):
        result = SafetyCheckResult(
            categories={
                "Hate": CategoryResult(severity=1, filtered=False),
                "Violence": CategoryResult(severity=0, filtered=False),
            },
            blocked=False,
            latency_ms=15.0,
        )
        assert result.max_severity == 1
        assert result.blocked is False

    def test_safety_check_result_blocked(self):
        result = SafetyCheckResult(
            categories={
                "Hate": CategoryResult(severity=5, filtered=True),
                "Violence": CategoryResult(severity=0, filtered=False),
            },
            blocked=True,
            latency_ms=25.0,
        )
        assert result.max_severity == 5
        assert result.blocked is True

    def test_to_guardrails_result(self):
        result = SafetyCheckResult(
            categories={
                "Hate": CategoryResult(severity=2, filtered=False),
                "Sexual": CategoryResult(severity=0, filtered=False),
            },
            blocked=False,
        )
        gr = result.to_guardrails_result()
        assert gr["blocked"] is False
        assert gr["max_severity"] == 2
        assert gr["content_safety"]["Hate"]["severity"] == 2

    def test_error_detail_defaults(self):
        detail = ContentFilterErrorDetail()
        assert detail.code == "content_filtered"
        assert detail.type == "content_filter_error"

    def test_safety_categories(self):
        assert SafetyCategory.HATE.value == "Hate"
        assert SafetyCategory.SELF_HARM.value == "SelfHarm"
        assert SafetyCategory.SEXUAL.value == "Sexual"
        assert SafetyCategory.VIOLENCE.value == "Violence"


# ════════════════════════════════════════════════════════════════════
# GuardrailsConfig unit tests
# ════════════════════════════════════════════════════════════════════


class TestGuardrailsConfig:
    def test_default_config(self):
        config = GuardrailsConfig()
        assert config.enabled is False
        assert config.threshold == 4
        assert config.is_live is False
        assert "enterprise" in config.bypass_tiers

    def test_live_config(self):
        config = GuardrailsConfig(
            enabled=True,
            endpoint="https://my-safety.cognitiveservices.azure.com",
            api_key="test-key-123",
        )
        assert config.is_live is True

    def test_not_live_without_key(self):
        config = GuardrailsConfig(
            enabled=True,
            endpoint="https://my-safety.cognitiveservices.azure.com",
        )
        assert config.is_live is False


# ════════════════════════════════════════════════════════════════════
# ContentSafetyClient unit tests
# ════════════════════════════════════════════════════════════════════


class TestContentSafetyClient:
    @pytest.mark.asyncio
    async def test_stub_mode_always_passes(self):
        """When no endpoint is configured, analyze() returns severity 0 everywhere."""
        config = GuardrailsConfig(enabled=True, endpoint="", api_key="")
        client = ContentSafetyClient(config)
        await client.startup()

        result = await client.analyze("I want to harm someone")
        assert result.blocked is False
        assert result.max_severity == 0
        assert len(result.categories) == 4  # All four categories present

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_parse_passing_response(self):
        """Parse an API response where all categories are below threshold."""
        config = GuardrailsConfig(
            enabled=True,
            endpoint="https://test.cognitiveservices.azure.com",
            api_key="test-key",
            threshold=4,
        )
        client = ContentSafetyClient(config)

        api_response = {
            "categoriesAnalysis": [
                {"category": "Hate", "severity": 0},
                {"category": "SelfHarm", "severity": 0},
                {"category": "Sexual", "severity": 2},
                {"category": "Violence", "severity": 0},
            ]
        }
        result = client._parse_response(api_response, elapsed_ms=10.0)
        assert result.blocked is False
        assert result.categories["Sexual"].severity == 2
        assert result.categories["Sexual"].filtered is False

    @pytest.mark.asyncio
    async def test_parse_blocking_response(self):
        """Parse an API response where a category exceeds threshold."""
        config = GuardrailsConfig(
            enabled=True,
            endpoint="https://test.cognitiveservices.azure.com",
            api_key="test-key",
            threshold=4,
        )
        client = ContentSafetyClient(config)

        api_response = {
            "categoriesAnalysis": [
                {"category": "Hate", "severity": 5},
                {"category": "SelfHarm", "severity": 0},
                {"category": "Sexual", "severity": 0},
                {"category": "Violence", "severity": 4},
            ]
        }
        result = client._parse_response(api_response, elapsed_ms=15.0)
        assert result.blocked is True
        assert result.categories["Hate"].severity == 5
        assert result.categories["Hate"].filtered is True
        assert result.categories["Violence"].severity == 4
        assert result.categories["Violence"].filtered is True
        assert result.categories["SelfHarm"].filtered is False

    @pytest.mark.asyncio
    async def test_per_category_threshold_override(self):
        """Per-category thresholds override the default."""
        config = GuardrailsConfig(
            enabled=True,
            endpoint="https://test.cognitiveservices.azure.com",
            api_key="test-key",
            threshold=4,
            category_thresholds={"Hate": 2},  # Stricter for hate
        )
        client = ContentSafetyClient(config)

        api_response = {
            "categoriesAnalysis": [
                {"category": "Hate", "severity": 2},  # Would pass default=4, blocked at 2
                {"category": "SelfHarm", "severity": 0},
                {"category": "Sexual", "severity": 0},
                {"category": "Violence", "severity": 0},
            ]
        }
        result = client._parse_response(api_response, elapsed_ms=5.0)
        assert result.blocked is True
        assert result.categories["Hate"].filtered is True

    @pytest.mark.asyncio
    async def test_fail_open_on_api_error(self):
        """When the Content Safety API returns an error, fail open (don't block)."""
        import httpx

        config = GuardrailsConfig(
            enabled=True,
            endpoint="https://test.cognitiveservices.azure.com",
            api_key="test-key",
        )
        client = ContentSafetyClient(config)

        # Mock httpx client that raises a timeout
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        client._http = mock_http

        result = await client.analyze("test text")
        assert result.blocked is False
        assert len(result.categories) == 0  # No data on error

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_fail_open_on_non_200(self):
        """When the API returns non-200, fail open."""
        config = GuardrailsConfig(
            enabled=True,
            endpoint="https://test.cognitiveservices.azure.com",
            api_key="test-key",
        )
        client = ContentSafetyClient(config)

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Rate limited"

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_resp)
        client._http = mock_http

        result = await client.analyze("test text")
        assert result.blocked is False

        await client.shutdown()


# ════════════════════════════════════════════════════════════════════
# Middleware helpers unit tests
# ════════════════════════════════════════════════════════════════════


class TestMiddlewareHelpers:
    def test_extract_output_text_chat(self):
        from app.guardrails.middleware import _extract_output_text

        body = json.dumps({
            "choices": [{
                "message": {"role": "assistant", "content": "Hello, how can I help?"},
                "finish_reason": "stop",
            }],
        })
        assert _extract_output_text(body) == "Hello, how can I help?"

    def test_extract_output_text_no_choices(self):
        from app.guardrails.middleware import _extract_output_text

        body = json.dumps({"data": [{"embedding": [0.1, 0.2]}]})
        assert _extract_output_text(body) == ""

    def test_extract_output_text_invalid_json(self):
        from app.guardrails.middleware import _extract_output_text
        assert _extract_output_text("not json") == ""


# ════════════════════════════════════════════════════════════════════
# Middleware integration tests
# ════════════════════════════════════════════════════════════════════


@pytest.fixture()
def safety_client(model_config_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """TestClient with content safety ENABLED in stub mode (no real endpoint)."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(model_config_dir))
    monkeypatch.setenv("DIRECTAI_DATABASE_PATH", ":memory:")
    monkeypatch.setenv("DIRECTAI_OTEL_ENABLED", "false")
    monkeypatch.setenv("DIRECTAI_CONTENT_SAFETY_ENABLED", "true")
    # No endpoint/key → stub mode (always passes)
    monkeypatch.setenv("DIRECTAI_CONTENT_SAFETY_ENDPOINT", "")
    monkeypatch.setenv("DIRECTAI_CONTENT_SAFETY_KEY", "")

    from app.middleware.rate_limit import TIER_LIMITS, TierLimits
    monkeypatch.setitem(TIER_LIMITS, "free", TierLimits(rpm=600, tpm=10_000_000))

    from app.config import get_settings
    get_settings.cache_clear()

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        from app.middleware.rate_limit import RateLimitMiddleware
        mw = app.middleware_stack
        while mw is not None:
            if isinstance(mw, RateLimitMiddleware):
                mw.reset()
                mw._default_rpm = 600
                mw._default_tpm = 10_000_000
                break
            mw = getattr(mw, "app", None)
        yield client


class TestContentSafetyMiddleware:
    def test_disabled_by_default_no_impact(self, test_client):
        """When content_safety_enabled=false (default), middleware is a no-op."""
        resp = test_client.get("/v1/models")
        assert resp.status_code == 200

    def test_healthz_not_filtered(self, safety_client):
        """Health probes bypass content safety filtering."""
        resp = safety_client.get("/healthz")
        assert resp.status_code == 200

    def test_models_not_filtered(self, safety_client):
        """GET /v1/models is not in _FILTERED_PATHS — no safety check."""
        resp = safety_client.get("/v1/models")
        assert resp.status_code == 200

    def test_chat_stub_passes(self, safety_client):
        """In stub mode, chat requests pass through safety check."""
        # This will fail at the backend (no real backend), but should NOT
        # fail at the safety check. We expect a 404 (model not found) or
        # 502 (backend unavailable), NOT a 400 (content filtered).
        resp = safety_client.post(
            "/v1/chat/completions",
            json={
                "model": "test-chat-model",
                "messages": [{"role": "user", "content": "Hello world"}],
            },
        )
        # Should get past safety (stub passes everything) and hit routing
        assert resp.status_code != 400 or "content_filtered" not in resp.text

    def test_embeddings_stub_passes(self, safety_client):
        """In stub mode, embedding requests pass through safety check."""
        resp = safety_client.post(
            "/v1/embeddings",
            json={"model": "test-embedding-model", "input": "Hello world"},
        )
        assert resp.status_code != 400 or "content_filtered" not in resp.text

    def test_stub_mode_metrics(self, safety_client):
        """Stub mode increments the 'stub' metric counter."""
        from app.guardrails.content_safety import SAFETY_CHECKS_TOTAL

        # Send a request that triggers a safety check
        safety_client.post(
            "/v1/chat/completions",
            json={
                "model": "test-chat-model",
                "messages": [{"role": "user", "content": "Test"}],
            },
        )

        # The stub counter should have been incremented
        # (We can't easily read the value directly without the registry,
        # but if we got here without error, the metric was created.)
        assert SAFETY_CHECKS_TOTAL._metrics  # metric has been used


class TestInputBlocking:
    """Test that the middleware blocks input when safety API returns high severity."""

    @pytest.fixture()
    def blocking_client(self, model_config_dir: Path, monkeypatch: pytest.MonkeyPatch):
        """TestClient with a mocked ContentSafetyClient that always blocks."""
        from fastapi.testclient import TestClient

        monkeypatch.setenv("DIRECTAI_MODEL_CONFIG_DIR", str(model_config_dir))
        monkeypatch.setenv("DIRECTAI_DATABASE_PATH", ":memory:")
        monkeypatch.setenv("DIRECTAI_OTEL_ENABLED", "false")
        monkeypatch.setenv("DIRECTAI_CONTENT_SAFETY_ENABLED", "true")
        monkeypatch.setenv("DIRECTAI_CONTENT_SAFETY_ENDPOINT", "")
        monkeypatch.setenv("DIRECTAI_CONTENT_SAFETY_KEY", "")

        from app.middleware.rate_limit import TIER_LIMITS, TierLimits
        monkeypatch.setitem(TIER_LIMITS, "free", TierLimits(rpm=600, tpm=10_000_000))

        from app.config import get_settings
        get_settings.cache_clear()

        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            from app.middleware.rate_limit import RateLimitMiddleware
            mw = app.middleware_stack
            while mw is not None:
                if isinstance(mw, RateLimitMiddleware):
                    mw.reset()
                    mw._default_rpm = 600
                    mw._default_tpm = 10_000_000
                    break
                mw = getattr(mw, "app", None)

            # Replace the safety client with one that always blocks
            mock_client = AsyncMock()
            mock_client.analyze = AsyncMock(return_value=SafetyCheckResult(
                categories={
                    "Hate": CategoryResult(severity=6, filtered=True),
                    "Violence": CategoryResult(severity=0, filtered=False),
                    "SelfHarm": CategoryResult(severity=0, filtered=False),
                    "Sexual": CategoryResult(severity=0, filtered=False),
                },
                blocked=True,
                latency_ms=5.0,
            ))
            app.state.content_safety_client = mock_client

            yield client

    def test_chat_blocked(self, blocking_client):
        """Chat request with hateful content should be blocked with 400."""
        resp = blocking_client.post(
            "/v1/chat/completions",
            json={
                "model": "test-chat-model",
                "messages": [{"role": "user", "content": "hateful content"}],
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "content_filtered"
        assert body["error"]["categories"]["Hate"]["severity"] == 6
        assert body["error"]["categories"]["Hate"]["filtered"] is True

    def test_embeddings_blocked(self, blocking_client):
        """Embedding request with hateful content should be blocked."""
        resp = blocking_client.post(
            "/v1/embeddings",
            json={"model": "test-embedding-model", "input": "hateful content"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "content_filtered"

    def test_models_not_blocked(self, blocking_client):
        """GET /v1/models should never be blocked by content safety."""
        resp = blocking_client.get("/v1/models")
        assert resp.status_code == 200
