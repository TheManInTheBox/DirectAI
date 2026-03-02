"""Tests for POST /v1/embeddings."""


def test_embedding_model_not_found(test_client):
    response = test_client.post(
        "/v1/embeddings",
        json={
            "model": "nonexistent-model",
            "input": "Hello world",
        },
    )
    assert response.status_code == 404


def test_embedding_wrong_modality(test_client):
    """Sending an embedding request to a chat model should return 400."""
    response = test_client.post(
        "/v1/embeddings",
        json={
            "model": "test-chat",
            "input": "Hello world",
        },
    )
    assert response.status_code == 400
    assert "chat" in response.json()["detail"].lower()
