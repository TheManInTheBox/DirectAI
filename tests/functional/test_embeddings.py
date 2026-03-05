"""POST /v1/embeddings — embedding inference tests."""

from __future__ import annotations

import httpx
import pytest


class TestEmbeddingSingle:
    """Single-input embedding requests."""

    def test_returns_200(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/v1/embeddings",
            json={"model": "bge-large-en-v1.5", "input": "Hello, world!"},
        )
        assert r.status_code == 200

    def test_response_shape(self, api_client: httpx.Client) -> None:
        body = api_client.post(
            "/v1/embeddings",
            json={"model": "bge-large-en-v1.5", "input": "Test sentence"},
        ).json()
        assert body["object"] == "list"
        assert len(body["data"]) == 1
        emb = body["data"][0]
        assert emb["object"] == "embedding"
        assert emb["index"] == 0
        assert isinstance(emb["embedding"], list)

    def test_dimension_1024(self, api_client: httpx.Client) -> None:
        body = api_client.post(
            "/v1/embeddings",
            json={"model": "bge-large-en-v1.5", "input": "Dimension check"},
        ).json()
        vec = body["data"][0]["embedding"]
        assert len(vec) == 1024, f"Expected 1024 dims, got {len(vec)}"

    def test_usage_reported(self, api_client: httpx.Client) -> None:
        body = api_client.post(
            "/v1/embeddings",
            json={"model": "bge-large-en-v1.5", "input": "Token count"},
        ).json()
        assert "usage" in body
        assert body["usage"]["prompt_tokens"] > 0
        assert body["usage"]["total_tokens"] > 0


class TestEmbeddingBatch:
    """Batch embedding requests."""

    def test_batch_two(self, api_client: httpx.Client) -> None:
        body = api_client.post(
            "/v1/embeddings",
            json={
                "model": "bge-large-en-v1.5",
                "input": ["First sentence.", "Second sentence."],
            },
        ).json()
        assert len(body["data"]) == 2
        assert body["data"][0]["index"] == 0
        assert body["data"][1]["index"] == 1

    def test_batch_dimensions_consistent(self, api_client: httpx.Client) -> None:
        body = api_client.post(
            "/v1/embeddings",
            json={
                "model": "bge-large-en-v1.5",
                "input": ["Alpha", "Bravo", "Charlie"],
            },
        ).json()
        dims = {len(d["embedding"]) for d in body["data"]}
        assert dims == {1024}, f"Not all embeddings are 1024-dim: {dims}"


class TestEmbeddingAlias:
    """Model name aliasing works for embeddings."""

    def test_namespaced_alias(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/v1/embeddings",
            json={"model": "baai/bge-large-en-v1.5", "input": "alias test"},
        )
        assert r.status_code == 200
        assert len(r.json()["data"][0]["embedding"]) == 1024


class TestEmbeddingErrors:
    """Error handling for embedding requests."""

    def test_unknown_model_404(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/v1/embeddings",
            json={"model": "nonexistent-model", "input": "test"},
        )
        assert r.status_code in (404, 400)

    def test_empty_input_rejected(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/v1/embeddings",
            json={"model": "bge-large-en-v1.5", "input": ""},
        )
        # Empty string should either work (some backends accept it) or 400
        assert r.status_code in (200, 400, 422)

    def test_missing_model_field(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/v1/embeddings",
            json={"input": "no model"},
        )
        assert r.status_code == 422
