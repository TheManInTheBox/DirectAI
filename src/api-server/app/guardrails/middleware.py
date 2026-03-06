"""
Content safety middleware — input/output filtering for inference requests.

Intercepts all inference requests:
  1. **Input filtering**: Extracts text from request body, runs through
     Content Safety API, blocks if any category exceeds threshold.
  2. **Output filtering**: For non-streaming responses, checks the full
     response text before returning. For streaming responses, accumulates
     chunks and checks at configured intervals.

Bypass: API keys with ``tier`` in ``bypass_tiers`` (default: Enterprise)
skip the block but still log safety scores for audit trail.

The middleware is a no-op when disabled (``DIRECTAI_CONTENT_SAFETY_ENABLED=false``).
"""

from __future__ import annotations

import json
import logging
import time
from typing import AsyncIterator, Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from app.guardrails.schemas import SafetyCheckResult

logger = logging.getLogger("directai.guardrails")

# Paths that need content safety checks (inference endpoints only)
_FILTERED_PATHS = frozenset({
    "/v1/chat/completions",
    "/v1/embeddings",
    "/v1/audio/transcriptions",
})

# Max request body size to read for safety check (prevent OOM)
_MAX_BODY_READ_BYTES = 2_097_152  # 2 MB


class ContentSafetyMiddleware(BaseHTTPMiddleware):
    """
    Input/output content safety filtering middleware.

    Requires ``app.state.content_safety_client`` (``ContentSafetyClient``)
    and ``app.state.guardrails_config`` (``GuardrailsConfig``) to be set
    during app startup.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        config = getattr(request.app.state, "guardrails_config", None)
        if config is None or not config.enabled:
            return await call_next(request)

        path = request.url.path
        if path not in _FILTERED_PATHS:
            return await call_next(request)

        client = getattr(request.app.state, "content_safety_client", None)
        if client is None:
            return await call_next(request)

        # ── Check bypass ────────────────────────────────────────────
        key_info = getattr(request.state, "key_info", None)
        bypass = False
        if key_info is not None and hasattr(key_info, "tier"):
            bypass = key_info.tier in config.bypass_tiers

        # ── Input filtering ─────────────────────────────────────────
        input_text = await _extract_input_text(request)
        if input_text:
            input_result = await client.analyze(input_text)
            # Stash on request.state for audit middleware to pick up
            request.state.content_safety_input = input_result

            if input_result.blocked and not bypass:
                logger.warning(
                    "Content blocked (input) — request_id=%s max_severity=%d",
                    getattr(request.state, "request_id", "-"),
                    input_result.max_severity,
                )
                return _make_block_response(input_result)

            if input_result.blocked and bypass:
                logger.info(
                    "Content safety bypass (input) — request_id=%s tier=%s max_severity=%d",
                    getattr(request.state, "request_id", "-"),
                    key_info.tier if key_info else "unknown",
                    input_result.max_severity,
                )

        # ── Forward to route handler ────────────────────────────────
        response = await call_next(request)

        # ── Output filtering ────────────────────────────────────────
        if not config.check_output:
            return response

        if isinstance(response, StreamingResponse):
            return _wrap_streaming_output(response, client, config, request, bypass)

        return await _check_non_streaming_output(response, client, config, request, bypass)


async def _extract_input_text(request: Request) -> str:
    """
    Extract human-readable text from the request body.

    For chat: concatenate all message contents.
    For embeddings: join input strings.
    For transcription: skip (audio binary, not text).
    """
    path = request.url.path

    if path == "/v1/audio/transcriptions":
        # Audio files — can't text-analyze binary. Skip input check.
        return ""

    try:
        body_bytes = await request.body()
        if len(body_bytes) > _MAX_BODY_READ_BYTES:
            return ""
        body = json.loads(body_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ""

    if path == "/v1/chat/completions":
        messages = body.get("messages", [])
        parts = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                # Multi-modal messages (text parts)
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(part.get("text", ""))
        return "\n".join(parts)

    if path == "/v1/embeddings":
        inp = body.get("input", "")
        if isinstance(inp, str):
            return inp
        if isinstance(inp, list):
            return "\n".join(str(i) for i in inp)

    return ""


def _make_block_response(result: SafetyCheckResult) -> JSONResponse:
    """Build an OpenAI-compatible 400 error for blocked content."""
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "message": "Content blocked by safety filter",
                "type": "content_filter_error",
                "code": "content_filtered",
                "categories": {
                    name: {"severity": cat.severity, "filtered": cat.filtered}
                    for name, cat in result.categories.items()
                },
            }
        },
    )


async def _check_non_streaming_output(
    response: Response,
    client,
    config,
    request: Request,
    bypass: bool,
) -> Response:
    """Check non-streaming response body for safety violations."""
    # Read full response body
    body_bytes = b""
    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
        if isinstance(chunk, str):
            body_bytes += chunk.encode("utf-8")
        else:
            body_bytes += chunk

    body_text = body_bytes.decode("utf-8", errors="replace")

    # Extract text from response JSON
    output_text = _extract_output_text(body_text)
    if not output_text:
        # No text to check — return original response
        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    result = await client.analyze(output_text)
    request.state.content_safety_output = result

    if result.blocked and not bypass:
        logger.warning(
            "Content blocked (output) — request_id=%s max_severity=%d",
            getattr(request.state, "request_id", "-"),
            result.max_severity,
        )
        return JSONResponse(
            status_code=200,
            content={
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "[Content filtered by safety policy]",
                        },
                        "finish_reason": "content_filter",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        )

    # Return original response
    return Response(
        content=body_bytes,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )


def _wrap_streaming_output(
    response: StreamingResponse,
    client,
    config,
    request: Request,
    bypass: bool,
) -> StreamingResponse:
    """
    Wrap a streaming response to periodically check accumulated text.

    Buffers ``stream_check_interval_chars`` characters before running a
    safety check. If the check triggers, the stream is terminated with
    a ``[Content filtered]`` marker and ``finish_reason: content_filter``.
    """

    async def checked_iterator() -> AsyncIterator[bytes]:
        accumulated_text = ""
        chars_since_check = 0
        blocked = False

        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            if blocked:
                break

            chunk_bytes = chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")
            chunk_str = chunk_bytes.decode("utf-8", errors="replace")

            # Extract text content from SSE data lines
            for line in chunk_str.split("\n"):
                if line.startswith("data: ") and line.strip() != "data: [DONE]":
                    try:
                        data = json.loads(line[6:])
                        delta = (
                            data.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            accumulated_text += delta
                            chars_since_check += len(delta)
                    except (json.JSONDecodeError, IndexError, KeyError):
                        pass

            # Periodic safety check on accumulated text
            if chars_since_check >= config.stream_check_interval_chars and accumulated_text:
                chars_since_check = 0
                result = await client.analyze(accumulated_text)
                request.state.content_safety_output = result

                if result.blocked and not bypass:
                    blocked = True
                    logger.warning(
                        "Content blocked (streaming output) — request_id=%s chars=%d",
                        getattr(request.state, "request_id", "-"),
                        len(accumulated_text),
                    )
                    # Yield a content_filter finish event
                    filter_event = json.dumps({
                        "choices": [{
                            "index": 0,
                            "delta": {"content": "\n\n[Content filtered by safety policy]"},
                            "finish_reason": "content_filter",
                        }]
                    })
                    yield f"data: {filter_event}\n\n".encode("utf-8")
                    yield b"data: [DONE]\n\n"
                    break

            yield chunk_bytes

        # Final check on remaining text if not already blocked
        if not blocked and accumulated_text and chars_since_check > 0:
            result = await client.analyze(accumulated_text)
            request.state.content_safety_output = result
            # At this point the stream is already sent — just log
            if result.blocked and not bypass:
                logger.warning(
                    "Content safety flagged AFTER stream completion — request_id=%s",
                    getattr(request.state, "request_id", "-"),
                )

    return StreamingResponse(
        checked_iterator(),
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )


def _extract_output_text(body_text: str) -> str:
    """Extract assistant message text from a non-streaming response body."""
    try:
        data = json.loads(body_text)
        choices = data.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        return content if isinstance(content, str) else ""
    except (json.JSONDecodeError, IndexError, KeyError):
        return ""
