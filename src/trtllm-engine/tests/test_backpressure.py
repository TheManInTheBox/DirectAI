"""Tests for backpressure — 429 when max_inflight_requests is exceeded."""

from __future__ import annotations


def test_backpressure_429(client):
    """
    When _inflight >= max_inflight_requests, the server returns 429.

    We patch _inflight directly since TestClient is synchronous and
    can't truly saturate the server with concurrent requests.
    """
    import engine.main as main_mod

    # max_inflight_requests is set to 4 in conftest env vars
    original = main_mod._inflight
    main_mod._inflight = 100  # way over the limit

    try:
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert resp.status_code == 429
        data = resp.json()
        assert data["error"]["type"] == "rate_limit_error"
        assert data["error"]["code"] == "rate_limit_exceeded"
        assert resp.headers.get("Retry-After") == "1"
    finally:
        main_mod._inflight = original


def test_under_limit_succeeds(client):
    """When under the limit, requests succeed normally."""
    import engine.main as main_mod

    main_mod._inflight = 0

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert resp.status_code == 200


def test_inflight_counter_resets_after_request(client):
    """_inflight should return to its pre-request value after completion."""
    import engine.main as main_mod

    before = main_mod._inflight

    client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert main_mod._inflight == before


def test_inflight_counter_resets_on_streaming(client):
    """_inflight should reset after a streaming request is fully consumed."""
    import engine.main as main_mod

    before = main_mod._inflight

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        },
    )
    # TestClient consumes the full response
    _ = resp.text
    assert main_mod._inflight == before
