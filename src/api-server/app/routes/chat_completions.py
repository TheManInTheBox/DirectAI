"""
POST /v1/chat/completions — OpenAI-compatible chat completion endpoint.

Supports both streaming (SSE) and non-streaming responses.
Proxies the request to the appropriate TensorRT-LLM backend.
"""

from __future__ import annotations

import json
import logging
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.auth import require_api_key
from app.metrics import INFLIGHT_REQUESTS, REQUEST_DURATION, REQUESTS_TOTAL, track_request
from app.routing.backend_client import CircuitOpenError
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def _check_backend_response(response, model: str) -> None:
    """Raise appropriate HTTPException for non-2xx backend responses."""
    if response.status_code < 400:
        return
    if response.status_code < 500:
        # Forward backend validation errors (4xx) to client
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)
    # 5xx from backend → translate to 502
    logger.error(
        "Backend returned %d for model '%s': %s",
        response.status_code, model, response.text[:500],
    )
    raise HTTPException(status_code=502, detail="Inference backend unavailable.")


@router.post(
    "/v1/chat/completions",
    response_model=ChatCompletionResponse,
    responses={
        404: {"description": "Model not found"},
        502: {"description": "Backend error"},
    },
)
async def create_chat_completion(
    body: ChatCompletionRequest,
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
    if model_spec.modality != "chat":
        raise HTTPException(
            status_code=400,
            detail=f"Model '{body.model}' is a {model_spec.modality} model, not a chat model.",
        )

    url = f"{model_spec.backend_url}/v1/chat/completions"
    headers = {"X-Request-ID": request_id}
    payload = body.model_dump(exclude_none=True)

    # ── Streaming ───────────────────────────────────────────────────
    if body.stream:

        async def event_stream():
            INFLIGHT_REQUESTS.labels(model=model_spec.name).inc()
            t_start = time.monotonic()
            status = "ok"
            try:
                async for chunk in backend.post_stream(url, payload, headers=headers):
                    yield chunk
            except Exception:
                status = "error"
                logger.exception("Stream error from backend for model '%s'", body.model)
                error_payload = json.dumps({"error": {"message": "Backend stream failed", "type": "server_error"}})
                yield f"data: {error_payload}\n\n".encode()
                yield b"data: [DONE]\n\n"
            finally:
                duration = time.monotonic() - t_start
                INFLIGHT_REQUESTS.labels(model=model_spec.name).dec()
                REQUEST_DURATION.labels(model=model_spec.name, method="chat").observe(duration)
                REQUESTS_TOTAL.labels(model=model_spec.name, method="chat", status=status).inc()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"X-Request-ID": request_id},
        )

    # ── Non-streaming ───────────────────────────────────────────────
    try:
        with track_request(model_spec.name, "chat"):
            response = await backend.post_json(url, payload, headers=headers)
        _check_backend_response(response, body.model)
        return response.json()
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
