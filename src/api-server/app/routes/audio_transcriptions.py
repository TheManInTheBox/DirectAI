"""
POST /v1/audio/transcriptions — OpenAI-compatible audio transcription endpoint.

Accepts multipart/form-data with an audio file.
Proxies the upload to the Whisper TensorRT-LLM backend.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
import httpx

from app.auth import require_api_key
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
    file: UploadFile = File(...),
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
        return response.json()
    except CircuitOpenError:
        raise HTTPException(
            status_code=503,
            detail=f"Backend for '{model}' is temporarily unavailable (circuit open).",
            headers={"Retry-After": "30"},
        )
    except (httpx.ConnectError, httpx.ConnectTimeout):
        logger.warning("Backend connect failed for model '%s' — may be scaling up", model)
        raise HTTPException(
            status_code=503,
            detail=f"Backend for '{model}' is starting up. Retry shortly.",
            headers={"Retry-After": "15"},
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Backend error for model '%s'", model)
        raise HTTPException(status_code=502, detail="Inference backend unavailable.")
