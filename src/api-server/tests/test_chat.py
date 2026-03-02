"""Tests for POST /v1/chat/completions."""


def test_chat_model_not_found(test_client):
    response = test_client.post(
        "/v1/chat/completions",
        json={
            "model": "nonexistent-model",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_chat_wrong_modality(test_client):
    """Sending a chat request to an embedding model should return 400."""
    response = test_client.post(
        "/v1/chat/completions",
        json={
            "model": "test-embed",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 400
    assert "embedding" in response.json()["detail"].lower()
