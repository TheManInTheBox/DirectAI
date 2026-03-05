"""
POST /v1/audio/transcriptions — OpenAI-compatible audio transcription endpoint.

Accepts multipart/form-data with an audio file.
Proxies the upload to the Whisper TensorRT-LLM backend.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.auth import require_api_key
from app.billing import emit_usage_event
from app.metrics import track_request
from app.routing.backend_client import CircuitOpenError
from app.schemas.audio import TranscriptionResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# 25 MB — matches OpenAI's audio transcription limit.
_MAX_AUDIO_BYTES = 25 * 1024 * 1024


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
    "/v1/audio/transcriptions",
    response_model=TranscriptionResponse,
    responses={
        404: {"description": "Model not found"},
        502: {"description": "Backend error"},
    },
)
async def create_transcription(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    model: str = Form(...),
    language: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    response_format: str | None = Form(default="json"),
    temperature: float | None = Form(default=None),
    _api_key: str = Depends(require_api_key),
):
    registry = request.app.state.model_registry
    backend = request.app.state.backend_client
    request_id = getattr(request.state, "request_id", "")

    # ── Resolve model ───────────────────────────────────────────────
    model_spec = registry.resolve(model)
    if model_spec is None:
        raise HTTPException(status_code=404, detail=f"Model '{model}' not found.")
    if model_spec.modality != "transcription":
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model}' is a {model_spec.modality} model, not a transcription model.",
        )

    url = f"{model_spec.backend_url}/v1/audio/transcriptions"
    headers = {"X-Request-ID": request_id}

    # ── Enforce file size limit ─────────────────────────────────
    # Read up to limit + 1 byte. If we get more, the file is too big.
    file_content = await file.read(_MAX_AUDIO_BYTES + 1)
    if len(file_content) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file exceeds {_MAX_AUDIO_BYTES // (1024 * 1024)}MB limit.",
        )
    files = {"file": (file.filename or "audio.wav", file_content, file.content_type or "audio/wav")}
    data: dict[str, str] = {"model": model}
    if language:
        data["language"] = language
    if prompt:
        data["prompt"] = prompt
    if response_format:
        data["response_format"] = response_format
    if temperature is not None:
        data["temperature"] = str(temperature)

    try:
        with track_request(model_spec.name, "transcription"):
            response = await backend.post_multipart(url, files=files, data=data, headers=headers)
        _check_backend_response(response, model)
        resp_data = response.json()

        # ── Usage metering (approximate: bytes → minutes) ───────────
        key_info = getattr(request.state, "key_info", None)
        if key_info is not None:
            # Rough estimate: audio_bytes / (16000 * 2) = seconds (16kHz 16-bit mono)
            audio_seconds = len(file_content) / 32000
            # Store as "output_tokens" = seconds * 100 (centiseconds for precision)
            key_store = getattr(request.app.state, "key_store", None)
            if key_store is not None:
                import asyncio
                asyncio.ensure_future(key_store.record_usage(
                    user_id=key_info.user_id,
                    api_key_id=key_info.key_id,
                    model=model_spec.name,
                    modality="transcription",
                    input_tokens=0,
                    output_tokens=int(audio_seconds * 100),
                    request_id=request_id or None,
                ))
            # Stripe metering — centiseconds of audio
            centiseconds = int(audio_seconds * 100)
            if centiseconds > 0:
                from app.config import get_settings as _get_settings
                _s = _get_settings()
                emit_usage_event(
                    tier=key_info.tier,
                    stripe_customer_id=key_info.stripe_customer_id,
                    event_name=_s.stripe_meter_transcription,
                    value=centiseconds,
                    idempotency_key=f"{request_id}:transcription:output",
                )

        return resp_data
    except CircuitOpenError:
        raise HTTPException(
            status_code=503,
            detail=f"Backend for '{model}' is temporarily unavailable (circuit open).",
            headers={"Retry-After": "30"},
        ) from None
    except (httpx.ConnectError, httpx.ConnectTimeout):
        logger.warning("Backend connect failed for model '%s' — may be scaling up", model)
        raise HTTPException(
            status_code=503,
            detail=f"Backend for '{model}' is starting up. Retry shortly.",
            headers={"Retry-After": "15"},
        ) from None
    except HTTPException:
        raise
    except Exception:
        logger.exception("Backend error for model '%s'", model)
        raise HTTPException(status_code=502, detail="Inference backend unavailable.") from None
