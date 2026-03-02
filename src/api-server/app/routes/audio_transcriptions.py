"""
POST /v1/audio/transcriptions — OpenAI-compatible audio transcription endpoint.

Accepts multipart/form-data with an audio file.
Proxies the upload to the Whisper TensorRT-LLM backend.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.auth import require_api_key
from app.metrics import track_request
from app.schemas.audio import TranscriptionResponse

logger = logging.getLogger(__name__)
router = APIRouter()


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

    # Build multipart payload for the backend
    file_content = await file.read()
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
        return response.json()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Backend error for model '%s'", model)
        raise HTTPException(status_code=502, detail="Inference backend unavailable.")
