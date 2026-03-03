"""Tests for /v1/chat/completions — non-streaming + streaming + usage."""

from __future__ import annotations

import json


# ── Non-streaming ───────────────────────────────────────────────────


def test_chat_non_streaming(client):
    """Stub runner returns a placeholder response."""
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["object"] == "chat.completion"
    assert data["model"] == "test-model"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert "stub" in data["choices"][0]["message"]["content"].lower()

    # Usage must be present
    assert data["usage"]["prompt_tokens"] == 5
    assert data["usage"]["completion_tokens"] == 0  # stub returns empty token_ids
    assert data["usage"]["total_tokens"] == 5


def test_chat_bad_messages_missing(client):
    """Missing 'messages' field → 400."""
    resp = client.post("/v1/chat/completions", json={"model": "x"})
    assert resp.status_code == 400


def test_chat_bad_messages_empty(client):
    """Empty messages list → 400."""
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "x", "messages": []},
    )
    assert resp.status_code == 400


def test_chat_bad_messages_type(client):
    """messages is not a list → 400."""
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "x", "messages": "hello"},
    )
    assert resp.status_code == 400


# ── Streaming ───────────────────────────────────────────────────────


def test_chat_streaming(client):
    """Stream=true should return SSE events ending with [DONE]."""
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    lines = resp.text.strip().split("\n")
    data_lines = [dl for dl in lines if dl.startswith("data: ")]

    # Must end with [DONE]
    assert data_lines[-1] == "data: [DONE]"

    # Parse all non-DONE chunks
    chunks = []
    for line in data_lines:
        payload = line.removeprefix("data: ")
        if payload == "[DONE]":
            continue
        chunks.append(json.loads(payload))

    assert len(chunks) >= 2  # at least some stub words + finish chunk

    # First chunk should have role
    assert chunks[0]["choices"][0]["delta"].get("role") == "assistant"

    # Last content chunk should have a finish_reason
    last_content_chunk = chunks[-1]
    assert last_content_chunk["choices"][0]["finish_reason"] is not None


def test_chat_streaming_include_usage(client):
    """stream_options.include_usage=true → usage chunk before [DONE]."""
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
            "stream_options": {"include_usage": True},
        },
    )
    assert resp.status_code == 200

    lines = resp.text.strip().split("\n")
    data_lines = [dl for dl in lines if dl.startswith("data: ")]

    # The line before [DONE] should be the usage chunk
    assert data_lines[-1] == "data: [DONE]"
    usage_line = data_lines[-2].removeprefix("data: ")
    usage_chunk = json.loads(usage_line)

    # Usage chunk has choices=[] and usage object (per OpenAI spec)
    assert usage_chunk["choices"] == []
    assert "usage" in usage_chunk
    assert usage_chunk["usage"]["prompt_tokens"] == 5
    assert usage_chunk["usage"]["completion_tokens"] >= 1  # stub produces tokens
    assert usage_chunk["usage"]["total_tokens"] == (
        usage_chunk["usage"]["prompt_tokens"] + usage_chunk["usage"]["completion_tokens"]
    )


def test_chat_streaming_no_usage_by_default(client):
    """Without stream_options, no usage chunk should appear."""
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        },
    )
    lines = resp.text.strip().split("\n")
    data_lines = [dl for dl in lines if dl.startswith("data: ")]

    # No chunk should have a "usage" key
    for line in data_lines:
        payload = line.removeprefix("data: ")
        if payload == "[DONE]":
            continue
        chunk = json.loads(payload)
        assert "usage" not in chunk
