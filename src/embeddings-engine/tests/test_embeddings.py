"""Tests for POST /v1/embeddings — single, batch, error cases."""

from __future__ import annotations

from tests.conftest import EMBED_DIM


def test_embed_single_text(client):
    """Single string input returns one embedding."""
    resp = client.post(
        "/v1/embeddings",
        json={"model": "test-embed-model", "input": "Hello world"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["object"] == "list"
    assert data["model"] == "test-embed-model"
    assert len(data["data"]) == 1
    assert data["data"][0]["object"] == "embedding"
    assert data["data"][0]["index"] == 0
    assert len(data["data"][0]["embedding"]) == EMBED_DIM

    # Usage should be present
    assert "usage" in data
    assert data["usage"]["prompt_tokens"] >= 1
    assert data["usage"]["total_tokens"] >= 1


def test_embed_batch(client):
    """List input returns multiple embeddings in order."""
    texts = ["First text", "Second text", "Third text"]
    resp = client.post(
        "/v1/embeddings",
        json={"model": "test-embed-model", "input": texts},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["data"]) == 3
    for i, item in enumerate(data["data"]):
        assert item["index"] == i
        assert len(item["embedding"]) == EMBED_DIM


def test_embed_embeddings_are_normalized(client):
    """Embeddings should be approximately L2 normalized."""
    import math

    resp = client.post(
        "/v1/embeddings",
        json={"model": "test-embed-model", "input": "test"},
    )
    data = resp.json()
    embedding = data["data"][0]["embedding"]

    norm = math.sqrt(sum(x * x for x in embedding))
    assert abs(norm - 1.0) < 0.01, f"Embedding L2 norm should be ~1.0, got {norm}"


def test_embed_empty_input(client):
    """Empty input list → 400."""
    resp = client.post(
        "/v1/embeddings",
        json={"model": "test-embed-model", "input": []},
    )
    assert resp.status_code == 400


def test_embed_exceeds_max_batch(client):
    """Input longer than max_batch_size → 400."""
    # max_batch_size is 32 in conftest env vars
    texts = [f"text-{i}" for i in range(33)]
    resp = client.post(
        "/v1/embeddings",
        json={"model": "test-embed-model", "input": texts},
    )
    assert resp.status_code == 400
    assert "exceeds" in resp.json()["detail"].lower()


def test_embed_missing_input(client):
    """Missing 'input' field → 422 (Pydantic validation)."""
    resp = client.post(
        "/v1/embeddings",
        json={"model": "test-embed-model"},
    )
    assert resp.status_code == 422
