"""
TRT-LLM inference server — OpenAI-compatible endpoints.

Supports two modalities controlled by TRTLLM_MODALITY:
  - "chat" (default) → POST /v1/chat/completions (streaming SSE + non-streaming)
  - "transcription"  → POST /v1/audio/transcriptions

This is the backend server that the DirectAI API server proxies to.
It runs inside an NVIDIA TRT-LLM container on AKS GPU nodes.

Common endpoints:
  GET  /v1/models  — list the single served model
  GET  /healthz    — liveness probe (always 200)
  GET  /readyz     — readiness probe (200 if engine loaded)
  GET  /metrics    — Prometheus metrics
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from engine.chat_format import (
    apply_chat_template,
    build_completion_response,
    build_stream_chunk,
    build_usage_chunk,
)
from engine.config import get_settings
from engine.metrics import (
    INFLIGHT_REQUESTS,
    PROMPT_TOKENS,
    REJECTED_REQUESTS,
    REQUEST_DURATION,
    REQUESTS_TOTAL,
    TOKENS_GENERATED,
    TTFT,
    metrics_content_type,
    metrics_response_body,
)
from engine.runner import TRTLLMRunner

logger = logging.getLogger(__name__)

# ── Global runner instance ──────────────────────────────────────────
_runner: TRTLLMRunner | None = None
# SAFETY: _inflight is safe as a bare int ONLY because uvicorn runs a
# single-event-loop (1 worker, 1 thread).  All increments/decrements happen
# inside async coroutines on that loop, so there is no concurrent mutation.
# If you EVER switch to multiple workers (--workers >1) or threads, replace
# this with an asyncio.Lock-guarded counter or an atomic from the threading
# module.  The backpressure gate in chat_completions relies on this counter
# being accurate — a race would silently allow overload or false-reject.
_inflight: int = 0


def _get_runner() -> TRTLLMRunner:
    if _runner is None or not _runner.is_loaded:
        raise HTTPException(status_code=503, detail="Engine not loaded")
    return _runner


# ── Lifespan ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runner
    settings = get_settings()

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )

    if settings.modality == "transcription":
        # ── Whisper mode ────────────────────────────────────────────
        from engine.whisper import register_whisper_routes

        logger.info("Modality: transcription — loading Whisper engine...")
        register_whisper_routes(
            app,
            engine_dir=settings.engine_dir,
            tokenizer_dir=settings.tokenizer_dir,
        )
        logger.info(
            "Whisper engine ready — serving as '%s'", settings.model_name
        )
        yield
        logger.info("Shutting down Whisper engine.")
    else:
        # ── Chat/LLM mode (default) ────────────────────────────────
        logger.info("Modality: chat — initializing TRT-LLM runner...")
        logger.info(
            "Config: model=%s  tp=%d  pp=%d  max_batch=%d  kv_cache=%.0f%%",
            settings.model_name,
            settings.tp_size,
            settings.pp_size,
            settings.max_batch_size,
            settings.kv_cache_free_gpu_mem_fraction * 100,
        )

        _runner = TRTLLMRunner(
            engine_dir=settings.engine_dir,
            tokenizer_dir=settings.tokenizer_dir,
            tp_size=settings.tp_size,
            pp_size=settings.pp_size,
            max_batch_size=settings.max_batch_size,
            max_input_len=settings.max_input_len,
            max_output_len=settings.max_output_len,
            max_beam_width=settings.max_beam_width,
            kv_cache_free_gpu_mem_fraction=settings.kv_cache_free_gpu_mem_fraction,
            enable_chunked_context=settings.enable_chunked_context,
        )
        _runner.load()

        logger.info("TRT-LLM engine ready — serving as '%s'", settings.model_name)
        yield

        logger.info("Shutting down TRT-LLM engine.")
        _runner = None


# ── App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="DirectAI TRT-LLM Engine",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


# ── POST /v1/chat/completions ──────────────────────────────────────
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    global _inflight
    body = await request.json()
    runner = _get_runner()
    settings = get_settings()

    # ── Backpressure gate ───────────────────────────────────────
    if _inflight >= settings.max_inflight_requests:
        REJECTED_REQUESTS.labels(reason="overloaded").inc()
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": "Server overloaded — too many concurrent requests.",
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded",
                }
            },
            headers={"Retry-After": "1"},
        )

    # ── Parse request ───────────────────────────────────────────
    messages = body.get("messages")
    if not messages or not isinstance(messages, list):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": "'messages' is required and must be a non-empty list.",
                    "type": "invalid_request_error",
                    "code": "invalid_messages",
                }
            },
        )

    stream = body.get("stream", False)
    max_tokens = body.get("max_tokens", 256)
    temperature = body.get("temperature", 1.0)
    top_p = body.get("top_p", 1.0)

    # stream_options — OpenAI spec: {"include_usage": true}
    stream_options = body.get("stream_options") or {}
    include_usage = bool(stream_options.get("include_usage", False)) and stream

    # Clamp to engine limits
    max_tokens = min(max_tokens, settings.max_output_len)

    # ── Apply chat template ────────────────────────────────────
    prompt = apply_chat_template(messages, runner.tokenizer)

    request_id = uuid.uuid4().hex

    if stream:
        return await _handle_streaming(
            runner, prompt, settings.model_name, request_id,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            include_usage=include_usage,
        )
    else:
        return await _handle_non_streaming(
            runner, prompt, settings.model_name, request_id,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )


async def _handle_non_streaming(
    runner: TRTLLMRunner,
    prompt: str,
    model_name: str,
    request_id: str,
    *,
    max_tokens: int,
    temperature: float,
    top_p: float,
) -> JSONResponse:
    """Handle non-streaming chat completion."""
    global _inflight
    _inflight += 1
    INFLIGHT_REQUESTS.inc()
    t_start = time.monotonic()

    try:
        loop = asyncio.get_running_loop()
        output = await loop.run_in_executor(
            None,
            lambda: runner.generate(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            ),
        )

        duration = time.monotonic() - t_start
        REQUEST_DURATION.observe(duration)
        PROMPT_TOKENS.inc(output.prompt_tokens)
        TOKENS_GENERATED.inc(output.completion_tokens)
        REQUESTS_TOTAL.labels(status="ok", stream="false").inc()

        response = build_completion_response(output, model_name, request_id)
        return JSONResponse(content=response)

    except Exception as exc:
        REQUESTS_TOTAL.labels(status="error", stream="false").inc()
        logger.exception("Generation failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": "Internal generation error.",
                    "type": "server_error",
                    "code": "generation_failed",
                }
            },
        )
    finally:
        INFLIGHT_REQUESTS.dec()
        _inflight -= 1


async def _handle_streaming(
    runner: TRTLLMRunner,
    prompt: str,
    model_name: str,
    request_id: str,
    *,
    max_tokens: int,
    temperature: float,
    top_p: float,
    include_usage: bool = False,
) -> StreamingResponse:
    """Handle streaming chat completion via SSE."""
    completion_id = f"chatcmpl-{request_id[:8]}"

    # Count prompt tokens up-front — needed for usage chunk
    prompt_tokens = len(runner.tokenizer.encode(prompt))

    async def event_stream():
        global _inflight
        _inflight += 1
        INFLIGHT_REQUESTS.inc()
        t_start = time.monotonic()
        t_first_token = None
        final_completion_tokens = 0

        try:
            first = True
            async for chunk in runner.generate_stream(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            ):
                if t_first_token is None and chunk.text:
                    t_first_token = time.monotonic()
                    TTFT.observe(t_first_token - t_start)

                # Track cumulative token count from the runner
                final_completion_tokens = chunk.completion_tokens

                data = build_stream_chunk(
                    chunk, model_name, completion_id,
                    include_role=first,
                )
                first = False

                yield f"data: {json.dumps(data)}\n\n"

                if chunk.finish_reason is not None:
                    break

            # Emit usage chunk when stream_options.include_usage is set
            if include_usage:
                usage_data = build_usage_chunk(
                    model_name,
                    completion_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=final_completion_tokens,
                )
                yield f"data: {json.dumps(usage_data)}\n\n"

            yield "data: [DONE]\n\n"

            duration = time.monotonic() - t_start
            REQUEST_DURATION.observe(duration)
            PROMPT_TOKENS.inc(prompt_tokens)
            TOKENS_GENERATED.inc(final_completion_tokens)
            REQUESTS_TOTAL.labels(status="ok", stream="true").inc()

        except Exception as exc:
            REQUESTS_TOTAL.labels(status="error", stream="true").inc()
            logger.exception("Streaming generation failed: %s", exc)
            error_data = {
                "error": {
                    "message": "Streaming generation error.",
                    "type": "server_error",
                    "code": "stream_failed",
                }
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            yield "data: [DONE]\n\n"

        finally:
            INFLIGHT_REQUESTS.dec()
            _inflight -= 1

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id,
        },
    )


# ── GET /v1/models ──────────────────────────────────────────────────
@app.get("/v1/models")
async def list_models():
    settings = get_settings()
    return {
        "object": "list",
        "data": [
            {
                "id": settings.model_name,
                "object": "model",
                "created": 0,
                "owned_by": "directai",
            }
        ],
    }


# ── Health probes ───────────────────────────────────────────────────
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    settings = get_settings()
    if settings.modality == "transcription":
        # Whisper mode — check if whisper module loaded
        from engine.whisper import _whisper

        if _whisper is None or not _whisper.is_loaded:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "detail": "Whisper engine not loaded"},
            )
        return {"status": "ready"}
    # Chat mode
    if _runner is None or not _runner.is_loaded:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "detail": "Engine not loaded"},
        )
    return {"status": "ready"}


# ── Metrics ─────────────────────────────────────────────────────────
@app.get("/metrics")
async def metrics():
    return Response(
        content=metrics_response_body(),
        media_type=metrics_content_type(),
    )


# ── Entrypoint ──────────────────────────────────────────────────────
if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "engine.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
