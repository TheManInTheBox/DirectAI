"""
POST /v1/embeddings — OpenAI-compatible embeddings endpoint.

Proxies the request to the ONNX Runtime embedding backend.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import require_api_key
from app.metrics import track_request
from app.schemas.embeddings import EmbeddingRequest, EmbeddingResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/v1/embeddings",
    response_model=EmbeddingResponse,
    responses={
        404: {"description": "Model not found"},
        502: {"description": "Backend error"},
    },
)
async def create_embedding(
    body: EmbeddingRequest,
    request: Request,
    _api_key: str = Depends(require_api_key),
):
    registry = request.app.state.model_registry
    backend = request.app.state.backend_client
    request_id = getattr(request.state, "request_id", "")

    # ── Resolve model ───────────────────────────────────────────────
    model_spec = registry.resolve(body.model)
    if model_spec is None:
        raise HTTPException(status_code=404, detail=f"Model '{body.model}' not found.")
    if model_spec.modality != "embedding":
        raise HTTPException(
            status_code=400,
            detail=f"Model '{body.model}' is a {model_spec.modality} model, not an embedding model.",
        )

    url = f"{model_spec.backend_url}/v1/embeddings"
    headers = {"X-Request-ID": request_id}
    payload = body.model_dump(exclude_none=True)

    try:
        with track_request(model_spec.name, "embedding"):
            response = await backend.post_json(url, payload, headers=headers)
        return response.json()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Backend error for model '%s'", body.model)
        raise HTTPException(status_code=502, detail="Inference backend unavailable.")
