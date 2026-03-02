"""Tests for health probes, /v1/models, and /metrics."""

from __future__ import annotations


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz_when_loaded(client):
    """readyz returns 200 when the engine is loaded (stub mode counts)."""
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
    assert data["data"][0]["id"] == "test-model"
    assert data["data"][0]["object"] == "model"
    assert data["data"][0]["owned_by"] == "directai"


def test_metrics_returns_prometheus(client):
    """GET /metrics returns Prometheus text format."""
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text

    # Check for our custom metrics
    assert "directai_llm_inflight_requests" in body
    assert "directai_llm_requests_total" in body
    assert "directai_llm_request_duration_seconds" in body
    assert "directai_llm_time_to_first_token_seconds" in body
    assert "directai_llm_tokens_generated_total" in body
    assert "directai_llm_prompt_tokens_total" in body
    assert "directai_llm_rejected_requests_total" in body


def test_metrics_after_request(client):
    """After a successful request, counters should increment."""
    # Make a request first
    client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )

    resp = client.get("/metrics")
    body = resp.text

    # The ok counter should have at least 1
    assert 'directai_llm_requests_total{status="ok",stream="false"}' in body
