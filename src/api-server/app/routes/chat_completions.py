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
from app.billing import emit_usage_event
from app.metrics import INFLIGHT_REQUESTS, REQUEST_DURATION, REQUESTS_TOTAL, track_request
from app.middleware.rate_limit import record_tokens
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
    payload["model"] = model_spec.name  # Canonical name for backend

    # ── Streaming ───────────────────────────────────────────────────
    if body.stream:
        async def event_stream():
            INFLIGHT_REQUESTS.labels(model=model_spec.name).inc()
            t_start = time.monotonic()
            status = "ok"
            completion_tokens = 0
            try:
                async for chunk in backend.post_stream(url, payload, headers=headers):
                    # Count tokens from SSE chunks
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode("utf-8", errors="ignore")
                    else:
                        chunk_str = chunk
                    for line in chunk_str.split("\n"):
                        if line.startswith("data: ") and line.strip() != "data: [DONE]":
                            try:
                                chunk_data = json.loads(line[6:])
                                for choice in chunk_data.get("choices", []):
                                    if choice.get("delta", {}).get("content"):
                                        completion_tokens += 1  # Approximate: 1 chunk ≈ 1 token
                            except (json.JSONDecodeError, KeyError):
                                pass
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
                # Record streaming usage
                key_info = getattr(request.state, "key_info", None)
                if key_info is not None and status == "ok":
                    # Record tokens against TPM rate limiter
                    record_tokens(request, completion_tokens)
                    key_store = getattr(request.app.state, "key_store", None)
                    if key_store is not None:
                        import asyncio
                        asyncio.ensure_future(key_store.record_usage(
                            user_id=key_info.user_id,
                            api_key_id=key_info.key_id,
                            model=model_spec.name,
                            modality="chat",
                            input_tokens=0,  # Unknown for streaming
                            output_tokens=completion_tokens,
                            request_id=request_id or None,
                        ))
                    # Stripe metering — output tokens only (input unknown for streaming)
                    settings = request.app.state._settings if hasattr(request.app.state, '_settings') else None
                    if settings is None:
                        from app.config import get_settings
                        settings = get_settings()
                    if completion_tokens > 0:
                        emit_usage_event(
                            tier=key_info.tier,
                            stripe_customer_id=key_info.stripe_customer_id,
                            event_name=settings.stripe_meter_chat_output,
                            value=completion_tokens,
                            idempotency_key=f"{request_id}:chat:output",
                        )

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
        data = response.json()

        # ── Usage metering ──────────────────────────────────────────
        key_info = getattr(request.state, "key_info", None)
        if key_info is None:
            logger.debug("Skipping usage metering — key_info not set on request.state")
        if key_info is not None:
            usage = data.get("usage", {})
            total_tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            # Record tokens against TPM rate limiter
            record_tokens(request, total_tokens)
            key_store = getattr(request.app.state, "key_store", None)
            if key_store is not None:
                import asyncio
                asyncio.ensure_future(key_store.record_usage(
                    user_id=key_info.user_id,
                    api_key_id=key_info.key_id,
                    model=model_spec.name,
                    modality="chat",
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    request_id=request_id or None,
                ))
            # Stripe metering — separate events for input and output tokens
            from app.config import get_settings as _get_settings
            _s = _get_settings()
            prompt_tok = usage.get("prompt_tokens", 0)
            completion_tok = usage.get("completion_tokens", 0)
            if prompt_tok > 0:
                queued = emit_usage_event(
                    tier=key_info.tier,
                    stripe_customer_id=key_info.stripe_customer_id,
                    event_name=_s.stripe_meter_chat_input,
                    value=prompt_tok,
                    idempotency_key=f"{request_id}:chat:input",
                )
                if not queued:
                    logger.debug(
                        "Meter event dropped for chat input: tier=%s, cust=%s, tokens=%d",
                        key_info.tier, key_info.stripe_customer_id[:8] if key_info.stripe_customer_id else "", prompt_tok,
                    )
            if completion_tok > 0:
                queued = emit_usage_event(
                    tier=key_info.tier,
                    stripe_customer_id=key_info.stripe_customer_id,
                    event_name=_s.stripe_meter_chat_output,
                    value=completion_tok,
                    idempotency_key=f"{request_id}:chat:output",
                )
                if not queued:
                    logger.debug(
                        "Meter event dropped for chat output: tier=%s, cust=%s, tokens=%d",
                        key_info.tier, key_info.stripe_customer_id[:8] if key_info.stripe_customer_id else "", completion_tok,
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
