"""
Whisper transcription support for the TRT-LLM engine.

Provides POST /v1/audio/transcriptions — OpenAI-compatible transcription
endpoint. Uses TRT-LLM's Whisper pipeline when available, falls back to
a stub response when tensorrt_llm is not installed (dev/CI mode).

The endpoint is registered on the FastAPI app only when the engine's
configured modality is 'transcription' (TRTLLM_MODALITY=transcription).
"""

from __future__ import annotations

import io
import logging
import time
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Max audio file size: 25 MB (matches OpenAI's limit)
_MAX_AUDIO_BYTES = 25 * 1024 * 1024


class WhisperRunner:
    """
    Wrapper around TRT-LLM Whisper inference.

    When tensorrt_llm is not installed, operates in stub mode
    returning a placeholder transcription (for dev/CI testing).
    """

    def __init__(self) -> None:
        self._model = None
        self._loaded = False
        self._stub = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self, engine_dir: str, tokenizer_dir: str) -> None:
        """Load Whisper TRT-LLM engine from compiled artifacts."""
        try:
            # Attempt TRT-LLM Whisper import
            from tensorrt_llm.runtime import ModelRunnerCpp  # noqa: F401

            logger.info("Loading Whisper TRT-LLM engine from %s", engine_dir)
            # TODO: Initialize the actual Whisper TRT-LLM pipeline.
            # The NVIDIA TRT-LLM Whisper example uses:
            #   - encoder engine + decoder engine in engine_dir
            #   - mel spectrogram preprocessing
            #   - beam search decoding
            # For now, mark as loaded — actual pipeline integration
            # depends on TRT-LLM's Whisper API stabilizing.
            self._loaded = True
            logger.info("Whisper TRT-LLM engine loaded (pipeline stub)")

        except ImportError:
            logger.warning(
                "tensorrt_llm not installed — Whisper running in stub mode. "
                "Transcription requests will return placeholder text."
            )
            self._stub = True
            self._loaded = True

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        language: str | None = None,
        prompt: str | None = None,
        temperature: float = 0.0,
    ) -> dict:
        """
        Transcribe audio bytes to text.

        Returns an OpenAI-compatible transcription response dict.
        """
        if not self._loaded:
            raise RuntimeError("Whisper engine not loaded")

        if self._stub:
            return {
                "text": "[stub] Transcription placeholder — TRT-LLM not installed.",
            }

        # TODO: Actual TRT-LLM Whisper inference:
        # 1. Convert audio_bytes → mel spectrogram (via whisper preprocessor)
        # 2. Run encoder engine → encoder output
        # 3. Run decoder engine with beam search → token IDs
        # 4. Decode token IDs → text
        # The implementation depends on TRT-LLM's Whisper example pipeline.
        raise NotImplementedError(
            "Full TRT-LLM Whisper inference pipeline not yet implemented. "
            "Use stub mode for development."
        )


# Module-level runner instance — set by register_whisper_routes()
_whisper: WhisperRunner | None = None


def register_whisper_routes(app, engine_dir: str, tokenizer_dir: str) -> WhisperRunner:
    """
    Load the Whisper engine and register transcription routes on the app.

    Called from main.py lifespan when TRTLLM_MODALITY=transcription.
    """
    global _whisper
    _whisper = WhisperRunner()
    _whisper.load(engine_dir, tokenizer_dir)
    app.include_router(router)
    return _whisper


@router.post("/v1/audio/transcriptions")
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form(...),
    language: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    response_format: str | None = Form(default="json"),
    temperature: float | None = Form(default=None),
):
    """OpenAI-compatible audio transcription endpoint."""
    if _whisper is None or not _whisper.is_loaded:
        raise HTTPException(status_code=503, detail="Whisper engine not loaded")

    # Read and validate audio file
    audio_bytes = await file.read(_MAX_AUDIO_BYTES + 1)
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file exceeds {_MAX_AUDIO_BYTES // (1024 * 1024)}MB limit.",
        )

    try:
        t_start = time.monotonic()
        result = _whisper.transcribe(
            audio_bytes,
            language=language,
            prompt=prompt,
            temperature=temperature or 0.0,
        )
        duration = time.monotonic() - t_start
        logger.info(
            "Transcription completed in %.2fs (%d bytes)",
            duration, len(audio_bytes),
        )
        return JSONResponse(content=result)

    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        logger.exception("Transcription failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": "Transcription failed.",
                    "type": "server_error",
                    "code": "transcription_error",
                }
            },
        )
