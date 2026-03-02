"""
Tests for X-Request-ID sanitization in CorrelationIdMiddleware.

Covers:
  - Clean IDs passed through unchanged
  - Unsafe characters stripped
  - Truncation at 128 chars
  - Empty-after-strip → UUID generated
  - Missing header → UUID generated
  - Pure Unicode/special chars → UUID generated
"""

from __future__ import annotations

import re

from starlette.testclient import TestClient
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from app.middleware.correlation_id import CorrelationIdMiddleware

_UUID_HEX = re.compile(r"^[0-9a-f]{32}$")


def _make_app() -> FastAPI:
    """Minimal app with only the CorrelationIdMiddleware."""
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/echo-id")
    async def echo_id(request: Request):
        return JSONResponse({"request_id": request.state.request_id})

    return app


_app = _make_app()
_client = TestClient(_app, raise_server_exceptions=False)


class TestCleanPassthrough:
    """Safe IDs should survive unchanged."""

    def test_simple_uuid(self):
        resp = _client.get("/echo-id", headers={"X-Request-ID": "abc-123_test.id"})
        assert resp.status_code == 200
        assert resp.headers["x-request-id"] == "abc-123_test.id"
        assert resp.json()["request_id"] == "abc-123_test.id"

    def test_all_allowed_chars(self):
        safe = "AZaz09-_."
        resp = _client.get("/echo-id", headers={"X-Request-ID": safe})
        assert resp.headers["x-request-id"] == safe


class TestUnsafeCharStripping:
    """Characters outside [a-zA-Z0-9\\-_.] are removed."""

    def test_spaces_stripped(self):
        resp = _client.get("/echo-id", headers={"X-Request-ID": "hello world"})
        assert resp.headers["x-request-id"] == "helloworld"

    def test_special_chars_stripped(self):
        resp = _client.get("/echo-id", headers={"X-Request-ID": "id<script>alert(1)</script>"})
        assert resp.headers["x-request-id"] == "idscriptalert1script"

    def test_slashes_stripped(self):
        resp = _client.get("/echo-id", headers={"X-Request-ID": "path/../../etc/passwd"})
        assert resp.headers["x-request-id"] == "path..etcpasswd"

    def test_newlines_stripped(self):
        resp = _client.get("/echo-id", headers={"X-Request-ID": "line1\nline2\r"})
        assert resp.headers["x-request-id"] == "line1line2"


class TestTruncation:
    """IDs longer than 128 chars are truncated."""

    def test_exact_128_not_truncated(self):
        long_id = "a" * 128
        resp = _client.get("/echo-id", headers={"X-Request-ID": long_id})
        assert resp.headers["x-request-id"] == long_id
        assert len(resp.headers["x-request-id"]) == 128

    def test_129_truncated(self):
        long_id = "b" * 200
        resp = _client.get("/echo-id", headers={"X-Request-ID": long_id})
        assert resp.headers["x-request-id"] == "b" * 128
        assert len(resp.headers["x-request-id"]) == 128


class TestAutoGeneration:
    """When no usable ID remains, a new UUID hex is generated."""

    def test_no_header_generates_uuid(self):
        resp = _client.get("/echo-id")
        rid = resp.headers["x-request-id"]
        assert _UUID_HEX.match(rid), f"Expected UUID hex, got: {rid}"

    def test_empty_string_generates_uuid(self):
        resp = _client.get("/echo-id", headers={"X-Request-ID": ""})
        rid = resp.headers["x-request-id"]
        assert _UUID_HEX.match(rid), f"Expected UUID hex, got: {rid}"

    def test_all_unsafe_chars_generates_uuid(self):
        """If stripping leaves nothing, generate a UUID."""
        resp = _client.get("/echo-id", headers={"X-Request-ID": "🔥💀🤖"})
        rid = resp.headers["x-request-id"]
        assert _UUID_HEX.match(rid), f"Expected UUID hex, got: {rid}"

    def test_only_spaces_generates_uuid(self):
        resp = _client.get("/echo-id", headers={"X-Request-ID": "   "})
        rid = resp.headers["x-request-id"]
        assert _UUID_HEX.match(rid), f"Expected UUID hex, got: {rid}"


class TestRequestState:
    """The sanitized ID must be available on request.state."""

    def test_state_matches_header(self):
        resp = _client.get("/echo-id", headers={"X-Request-ID": "state-check-42"})
        assert resp.json()["request_id"] == "state-check-42"
        assert resp.headers["x-request-id"] == "state-check-42"

    def test_auto_generated_in_state(self):
        resp = _client.get("/echo-id")
        rid = resp.json()["request_id"]
        assert _UUID_HEX.match(rid)
        assert resp.headers["x-request-id"] == rid
