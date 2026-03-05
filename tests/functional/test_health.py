"""Health and readiness probe tests."""

from __future__ import annotations

import httpx


class TestHealthz:
    """GET /healthz — liveness probe."""

    def test_returns_200(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/healthz")
        assert r.status_code == 200

    def test_body_contains_status_ok(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/healthz")
        body = r.json()
        assert body["status"] == "ok"

    def test_no_auth_required(self, anon_client: httpx.Client) -> None:
        """Healthz must be accessible without a Bearer token."""
        r = anon_client.get("/healthz")
        assert r.status_code == 200


class TestReadyz:
    """GET /readyz — readiness probe."""

    def test_returns_200_or_503(self, anon_client: httpx.Client) -> None:
        """Readyz returns 200 when all backends are up, 503 if any are down."""
        r = anon_client.get("/readyz")
        assert r.status_code in (200, 503)

    def test_body_has_models_count(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/readyz")
        body = r.json()
        assert "models" in body
        assert isinstance(body["models"], int)
        assert body["models"] >= 1, "Expected at least 1 model registered"

    def test_body_has_backends_map(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/readyz")
        body = r.json()
        assert "backends" in body
        assert isinstance(body["backends"], dict)

    def test_embeddings_backend_healthy(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/readyz")
        backends = r.json()["backends"]
        assert "bge-large-en-v1-5" in backends, f"Expected bge-large-en-v1-5 in backends, got {list(backends.keys())}"
        assert backends["bge-large-en-v1-5"] is True, "Embeddings backend should be healthy"

    def test_no_auth_required(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/readyz")
        assert r.status_code in (200, 503)


class TestMetrics:
    """GET /metrics — Prometheus metrics endpoint."""

    def test_returns_200(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/metrics")
        assert r.status_code == 200

    def test_content_type_is_text(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/metrics")
        assert "text/plain" in r.headers.get("content-type", "") or "text/plain" in r.text[:100]

    def test_contains_directai_metrics(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/metrics")
        text = r.text
        assert "directai_" in text or "http_" in text, "Expected Prometheus metrics with directai_ or http_ prefix"
