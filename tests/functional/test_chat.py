"""POST /v1/chat/completions — LLM inference tests."""

from __future__ import annotations

import json

import httpx
import pytest

MODEL = "qwen2.5-3b-instruct"


class TestChatSync:
    """Non-streaming chat completions."""

    def test_returns_200(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "Say hello."}],
                "max_tokens": 16,
            },
            timeout=60,
        )
        assert r.status_code == 200

    def test_response_shape(self, api_client: httpx.Client) -> None:
        body = api_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "Reply with OK."}],
                "max_tokens": 8,
            },
            timeout=60,
        ).json()
        assert body["object"] == "chat.completion"
        assert len(body["choices"]) >= 1
        choice = body["choices"][0]
        assert "message" in choice
        assert choice["message"]["role"] == "assistant"
        assert isinstance(choice["message"]["content"], str)
        assert len(choice["message"]["content"]) > 0

    def test_finish_reason(self, api_client: httpx.Client) -> None:
        body = api_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 4,
            },
            timeout=60,
        ).json()
        reason = body["choices"][0]["finish_reason"]
        assert reason in ("stop", "length"), f"Unexpected finish_reason: {reason}"

    def test_usage_present(self, api_client: httpx.Client) -> None:
        body = api_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "Count."}],
                "max_tokens": 8,
            },
            timeout=60,
        ).json()
        assert "usage" in body
        assert body["usage"]["prompt_tokens"] > 0
        assert body["usage"]["completion_tokens"] > 0
        assert body["usage"]["total_tokens"] == (
            body["usage"]["prompt_tokens"] + body["usage"]["completion_tokens"]
        )

    def test_model_echoed(self, api_client: httpx.Client) -> None:
        body = api_client.post(
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "Echo."}],
                "max_tokens": 4,
            },
            timeout=60,
        ).json()
        # The model field in the response may be the backend name, not the alias
        assert "model" in body
        assert isinstance(body["model"], str)


class TestChatStreaming:
    """Streaming (SSE) chat completions."""

    def test_stream_returns_200(self, api_client: httpx.Client) -> None:
        with api_client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "Say hi."}],
                "max_tokens": 16,
                "stream": True,
            },
            timeout=60,
        ) as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers.get("content-type", "")

    def test_stream_yields_chunks(self, api_client: httpx.Client) -> None:
        chunks: list[dict] = []
        with api_client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "Count to 3."}],
                "max_tokens": 32,
                "stream": True,
            },
            timeout=60,
        ) as r:
            for line in r.iter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    chunks.append(json.loads(line[6:]))

        assert len(chunks) >= 1, "Expected at least one SSE chunk"
        # First chunk should have a delta
        assert chunks[0]["object"] == "chat.completion.chunk"
        assert "choices" in chunks[0]

    def test_stream_ends_with_done(self, api_client: httpx.Client) -> None:
        lines: list[str] = []
        with api_client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "Bye."}],
                "max_tokens": 8,
                "stream": True,
            },
            timeout=60,
        ) as r:
            for line in r.iter_lines():
                if line.strip():
                    lines.append(line)

        assert lines[-1] == "data: [DONE]", f"Last line was: {lines[-1]}"


class TestChatAlias:
    """Model name aliasing works for chat."""

    def test_namespaced_alias(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/v1/chat/completions",
            json={
                "model": "qwen/qwen2.5-3b-instruct",
                "messages": [{"role": "user", "content": "OK"}],
                "max_tokens": 4,
            },
            timeout=60,
        )
        assert r.status_code == 200


class TestChatErrors:
    """Error handling for chat requests."""

    def test_unknown_model(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/v1/chat/completions",
            json={
                "model": "nonexistent-model",
                "messages": [{"role": "user", "content": "Hi"}],
            },
        )
        assert r.status_code in (404, 400)

    def test_missing_messages(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/v1/chat/completions",
            json={"model": MODEL},
        )
        assert r.status_code == 422

    def test_empty_messages(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/v1/chat/completions",
            json={"model": MODEL, "messages": []},
        )
        # Should either 400/422 or pass through to backend which may error
        assert r.status_code in (200, 400, 422)
