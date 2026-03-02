"""
POST /v1/embeddings — OpenAI-compatible embeddings endpoint.

Proxies the request to the ONNX Runtime embedding backend.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
import httpx

from app.auth import require_api_key
from app.metrics import track_request
from app.routing.backend_client import CircuitOpenError
from app.schemas.embeddings import EmbeddingRequest, EmbeddingResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def _check_backend_response(response, model: str) -> None:
    """Raise appropriate HTTPException for non-2xx backend responses."""
    if response.status_code < 400:
        return
    if response.status_code < 500:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)
    logger.error(
        "Backend returned %d for model '%s': %s",
        response.status_code, model, response.text[:500],
    )
    raise HTTPException(status_code=502, detail="Inference backend unavailable.")


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
        _check_backend_response(response, body.model)
        return response.json()
    except CircuitOpenError:
        raise HTTPException(
            status_code=503,
            detail=f"Backend for '{body.model}' is temporarily unavailable (circuit open).",
            headers={"Retry-After": "30"},
        )
    except (httpx.ConnectError, httpx.ConnectTimeout):
        logger.warning("Backend connect failed for model '%s' — may be scaling up", body.model)
        raise HTTPException(
            status_code=503,
            detail=f"Backend for '{body.model}' is starting up. Retry shortly.",
            headers={"Retry-After": "15"},
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Backend error for model '%s'", body.model)
        raise HTTPException(status_code=502, detail="Inference backend unavailable.")
