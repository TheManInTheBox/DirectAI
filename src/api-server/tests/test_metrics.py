"""Tests for /metrics Prometheus endpoint."""


def test_metrics_endpoint(test_client):
    response = test_client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"] or "text/plain" in response.headers.get("content-type", "")
    body = response.text
    # Verify our custom metrics are registered
    assert "directai_backend_inflight_requests" in body
    assert "directai_requests_total" in body
    assert "directai_request_duration_seconds" in body
