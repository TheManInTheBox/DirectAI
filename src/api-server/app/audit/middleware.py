"""
Audit middleware — request/response capture for compliance logging.

Captures every inference request (/v1/*) as a structured AuditRecord
and pushes it onto the AuditWriter queue. The actual write happens
asynchronously — this middleware adds ZERO latency to the request path.

For streaming responses, the middleware wraps the response body iterator
to accumulate the full output text. If the client disconnects mid-stream,
the partial response is still recorded with ``finish_reason='client_disconnect'``.

Non-inference paths (healthz, readyz, metrics, docs) are excluded.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import AsyncIterator, Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from app.audit.schemas import AuditInputSummary, AuditOutputSummary, AuditRecord

logger = logging.getLogger("directai.audit")

# Paths that produce audit records (inference + native API)
_AUDITED_PREFIXES = ("/v1/", "/api/v1/")

# Paths explicitly excluded (health probes, metrics, docs)
_EXCLUDED_PATHS = frozenset({"/healthz", "/readyz", "/metrics", "/docs", "/openapi.json"})

# Max body size to capture (prevent OOM on huge payloads)
_MAX_BODY_CAPTURE_BYTES = 1_048_576  # 1 MB


def _hash_ip(ip: str) -> str:
    """One-way hash of client IP for privacy compliance."""
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]


def _should_audit(path: str) -> bool:
    """Decide whether a request path should generate an audit record."""
    if path in _EXCLUDED_PATHS:
        return False
    return any(path.startswith(prefix) for prefix in _AUDITED_PREFIXES)


def _extract_modality(path: str) -> Optional[str]:
    """Infer modality from request path."""
    if "chat/completions" in path:
        return "chat"
    if "embeddings" in path:
        return "embedding"
    if "audio/transcriptions" in path:
        return "transcription"
    return None


def _count_input_tokens_estimate(body: dict) -> tuple[int, int]:
    """Rough input token/message count from request body.

    Returns (estimated_token_count, message_count).
    This is a fast heuristic — not a tokenizer call.
    ~4 chars per token is the standard English approximation.
    """
    messages = body.get("messages", [])
    message_count = len(messages)

    # Chat: sum content length across messages
    total_chars = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            # Multi-modal: content parts
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total_chars += len(part.get("text", ""))

    # Embeddings: input can be string or list of strings
    inp = body.get("input", "")
    if isinstance(inp, str):
        total_chars += len(inp)
    elif isinstance(inp, list):
        for item in inp:
            if isinstance(item, str):
                total_chars += len(item)
        message_count = len(inp)

    return (max(1, total_chars // 4), message_count)


def _extract_output_tokens(response_body: str) -> tuple[int, Optional[str]]:
    """Extract output token count and finish reason from response JSON."""
    try:
        data = json.loads(response_body)
        usage = data.get("usage", {})
        output_tokens = usage.get("completion_tokens", 0) or usage.get("total_tokens", 0)
        finish_reason = None
        choices = data.get("choices", [])
        if choices:
            finish_reason = choices[0].get("finish_reason")
        return (output_tokens, finish_reason)
    except (json.JSONDecodeError, TypeError, AttributeError):
        return (0, None)


class AuditMiddleware(BaseHTTPMiddleware):
    """Captures request/response data and enqueues audit records.

    Must be added AFTER CorrelationIdMiddleware (so request_id is available)
    and BEFORE RequestLoggingMiddleware in the middleware stack.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        if not _should_audit(path):
            return await call_next(request)

        # ── Capture request ─────────────────────────────────────────
        start_time = time.perf_counter()
        request_body: Optional[dict] = None

        try:
            if request.method in ("POST", "PUT", "PATCH"):
                body_bytes = await request.body()
                if len(body_bytes) <= _MAX_BODY_CAPTURE_BYTES:
                    try:
                        request_body = json.loads(body_bytes)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_body = None
        except Exception:
            pass  # Body might not be readable (multipart, etc.)

        # ── Execute request ─────────────────────────────────────────
        response = await call_next(request)

        # ── Capture response + build audit record ───────────────────
        latency_ms = (time.perf_counter() - start_time) * 1000
        request_id = getattr(request.state, "request_id", "unknown")

        # Auth context
        key_info = getattr(request.state, "key_info", None)
        user_id = key_info.user_id if key_info else None
        api_key_id = key_info.key_id if key_info else None
        api_key_prefix = None
        if key_info and hasattr(key_info, "name"):
            api_key_prefix = key_info.name[:12] if key_info.name else None

        # Model info (set by route handlers on request.state)
        model = getattr(request.state, "audit_model", None)
        modality = _extract_modality(path)

        # Input summary
        input_tokens, message_count = (0, 0)
        if request_body:
            input_tokens, message_count = _count_input_tokens_estimate(request_body)

        # Client metadata
        client_ip = request.client.host if request.client else None
        hashed_ip = _hash_ip(client_ip) if client_ip else None
        user_agent = request.headers.get("user-agent", "")[:200]

        # ── Handle streaming vs non-streaming ───────────────────────
        if isinstance(response, StreamingResponse):
            # Wrap the stream to capture output
            original_body = response.body_iterator
            captured_chunks: list[str] = []
            output_tokens = 0
            finish_reason: Optional[str] = None
            is_partial = False

            async def audited_stream() -> AsyncIterator[bytes]:
                nonlocal output_tokens, finish_reason, is_partial
                try:
                    async for chunk in original_body:
                        if isinstance(chunk, bytes):
                            chunk_str = chunk.decode("utf-8", errors="ignore")
                        else:
                            chunk_str = chunk
                        captured_chunks.append(chunk_str)

                        # Count tokens from SSE data lines
                        for line in chunk_str.split("\n"):
                            if line.startswith("data: ") and line.strip() != "data: [DONE]":
                                try:
                                    chunk_data = json.loads(line[6:])
                                    for choice in chunk_data.get("choices", []):
                                        delta = choice.get("delta", {})
                                        if delta.get("content"):
                                            output_tokens += 1
                                        fr = choice.get("finish_reason")
                                        if fr:
                                            finish_reason = fr
                                except (json.JSONDecodeError, KeyError):
                                    pass

                        yield chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")
                except GeneratorExit:
                    # Client disconnected mid-stream
                    is_partial = True
                    finish_reason = "client_disconnect"
                except Exception:
                    is_partial = True
                    finish_reason = "error"
                    raise
                finally:
                    # Enqueue audit record after stream completes
                    final_latency = (time.perf_counter() - start_time) * 1000
                    record = AuditRecord(
                        request_id=request_id,
                        user_id=user_id,
                        api_key_id=api_key_id,
                        api_key_prefix=api_key_prefix,
                        method=request.method,
                        path=path,
                        model=model,
                        modality=modality,
                        input_summary=AuditInputSummary(
                            token_count=input_tokens,
                            message_count=message_count,
                        ),
                        output_summary=AuditOutputSummary(
                            token_count=output_tokens,
                            finish_reason=finish_reason,
                            is_partial=is_partial,
                        ),
                        latency_ms=final_latency,
                        status_code=response.status_code,
                        ip_address=hashed_ip,
                        user_agent=user_agent,
                        request_body=request_body,
                        response_body="".join(captured_chunks) if captured_chunks else None,
                    )
                    _enqueue_audit(request, record)

            response.body_iterator = audited_stream()
            return response
        else:
            # Non-streaming: capture response body
            response_body_text: Optional[str] = None
            if hasattr(response, "body"):
                try:
                    response_body_text = response.body.decode("utf-8", errors="ignore")
                except Exception:
                    pass

            output_tokens_count = 0
            finish_reason_val: Optional[str] = None
            if response_body_text:
                output_tokens_count, finish_reason_val = _extract_output_tokens(response_body_text)

            record = AuditRecord(
                request_id=request_id,
                user_id=user_id,
                api_key_id=api_key_id,
                api_key_prefix=api_key_prefix,
                method=request.method,
                path=path,
                model=model,
                modality=modality,
                input_summary=AuditInputSummary(
                    token_count=input_tokens,
                    message_count=message_count,
                ),
                output_summary=AuditOutputSummary(
                    token_count=output_tokens_count,
                    finish_reason=finish_reason_val,
                    is_partial=False,
                ),
                latency_ms=latency_ms,
                status_code=response.status_code,
                ip_address=hashed_ip,
                user_agent=user_agent,
                request_body=request_body,
                response_body=response_body_text,
            )
            _enqueue_audit(request, record)
            return response


def _enqueue_audit(request: Request, record: AuditRecord) -> None:
    """Push audit record onto the writer queue (fire-and-forget)."""
    try:
        writer = getattr(request.app.state, "audit_writer", None)
        if writer is not None:
            writer.enqueue(record)
    except Exception:
        logger.exception("Failed to enqueue audit record %s", record.request_id)
