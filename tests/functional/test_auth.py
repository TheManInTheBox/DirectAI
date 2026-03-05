"""Authentication and authorization tests."""

from __future__ import annotations

import httpx


class TestAuthRequired:
    """Endpoints that require a Bearer token must reject unauthenticated requests."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/v1/models"),
        ("POST", "/v1/embeddings"),
        ("POST", "/v1/chat/completions"),
    ]

    def test_models_requires_auth(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/v1/models")
        assert r.status_code == 401

    def test_embeddings_requires_auth(self, anon_client: httpx.Client) -> None:
        r = anon_client.post("/v1/embeddings", json={"input": "test", "model": "bge-large-en-v1.5"})
        assert r.status_code == 401

    def test_chat_requires_auth(self, anon_client: httpx.Client) -> None:
        r = anon_client.post(
            "/v1/chat/completions",
            json={"model": "qwen2.5-3b-instruct", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
        )
        assert r.status_code == 401

    def test_401_includes_www_authenticate_header(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/v1/models")
        assert r.status_code == 401
        assert "bearer" in r.headers.get("www-authenticate", "").lower()

    def test_401_body_is_json(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/v1/models")
        body = r.json()
        assert "detail" in body


class TestInvalidKey:
    """Invalid API keys must be rejected."""

    def test_invalid_key_returns_401(self, anon_client: httpx.Client) -> None:
        r = anon_client.get(
            "/v1/models",
            headers={"Authorization": "Bearer dai_sk_this_key_does_not_exist_at_all"},
        )
        assert r.status_code == 401

    def test_empty_bearer_returns_401(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/v1/models", headers={"Authorization": "Bearer x"})
        assert r.status_code == 401

    def test_malformed_auth_header_returns_401_or_403(self, anon_client: httpx.Client) -> None:
        r = anon_client.get("/v1/models", headers={"Authorization": "Token abc123"})
        assert r.status_code in (401, 403)


class TestValidKey:
    """Valid API key grants access."""

    def test_models_returns_200(self, api_client: httpx.Client) -> None:
        r = api_client.get("/v1/models")
        assert r.status_code == 200


class TestResponseHeaders:
    """Every response should include correlation/security headers."""

    def test_request_id_header_present(self, api_client: httpx.Client) -> None:
        r = api_client.get("/v1/models")
        assert "x-request-id" in r.headers, "Expected X-Request-ID header"

    def test_client_request_id_echoed(self, api_client: httpx.Client) -> None:
        r = api_client.get("/v1/models", headers={"X-Request-ID": "func-test-123"})
        assert r.headers.get("x-request-id") == "func-test-123"
