"""
POST /v1/embeddings — OpenAI-compatible embeddings endpoint.

Proxies the request to the ONNX Runtime embedding backend.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import require_api_key
from app.billing import emit_usage_event
from app.metrics import track_request
from app.middleware.rate_limit import record_tokens
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
    payload["model"] = model_spec.name  # Canonical name for backend

    try:
        with track_request(model_spec.name, "embedding"):
            response = await backend.post_json(url, payload, headers=headers)
        _check_backend_response(response, body.model)
        data = response.json()

        # ── Usage metering ──────────────────────────────────────────
        key_info = getattr(request.state, "key_info", None)
        if key_info is not None:
            usage = data.get("usage", {})
            total_tokens = usage.get("total_tokens", usage.get("prompt_tokens", 0))
            # Record tokens against TPM rate limiter
            record_tokens(request, total_tokens)
            key_store = getattr(request.app.state, "key_store", None)
            if key_store is not None:
                import asyncio
                asyncio.ensure_future(key_store.record_usage(
                    user_id=key_info.user_id,
                    api_key_id=key_info.key_id,
                    model=model_spec.name,
                    modality="embedding",
                    input_tokens=usage.get("total_tokens", usage.get("prompt_tokens", 0)),
                    output_tokens=0,
                    request_id=request_id or None,
                ))
            # Stripe metering — embedding tokens
            if total_tokens > 0:
                from app.config import get_settings as _get_settings
                _s = _get_settings()
                emit_usage_event(
                    tier=key_info.tier,
                    stripe_customer_id=key_info.stripe_customer_id,
                    event_name=_s.stripe_meter_embedding,
                    value=total_tokens,
                    idempotency_key=f"{request_id}:embedding:input",
                )

        return data
    except CircuitOpenError:
        raise HTTPException(
            status_code=503,
            detail=f"Backend for '{body.model}' is temporarily unavailable (circuit open).",
            headers={"Retry-After": "30"},
        ) from None
    except (httpx.ConnectError, httpx.ConnectTimeout):
        logger.warning("Backend connect failed for model '%s' — may be scaling up", body.model)
        raise HTTPException(
            status_code=503,
            detail=f"Backend for '{body.model}' is starting up. Retry shortly.",
            headers={"Retry-After": "15"},
        ) from None
    except HTTPException:
        raise
    except Exception:
        logger.exception("Backend error for model '%s'", body.model)
        raise HTTPException(status_code=502, detail="Inference backend unavailable.") from None
