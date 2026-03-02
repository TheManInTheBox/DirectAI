"""Tests for health probes, /v1/models, and /metrics."""

from __future__ import annotations


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz_when_loaded(client):
    """readyz returns 200 when the model is loaded (mock = always loaded)."""
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_models_lists_configured_model(client):
    """GET /v1/models returns the model name from config."""
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()

    assert data["object"] == "list"
    assert len(data["data"]) == 1
    assert data["data"][0]["id"] == "test-embed-model"
    assert data["data"][0]["object"] == "model"
    assert data["data"][0]["owned_by"] == "directai"


def test_metrics_returns_prometheus(client):
    """GET /metrics returns Prometheus text format with our custom metrics."""
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text

    assert "directai_embed_inflight_requests" in body
    assert "directai_embed_requests_total" in body
    assert "directai_embed_request_duration_seconds" in body
    assert "directai_embed_batch_size" in body
    assert "directai_embed_tokens_processed_total" in body


def test_metrics_after_request(client):
    """After a successful embed, counters should increment."""
    client.post(
        "/v1/embeddings",
        json={"model": "test-embed-model", "input": "hello"},
    )

    resp = client.get("/metrics")
    body = resp.text

    assert 'directai_embed_requests_total{status="ok"}' in body
