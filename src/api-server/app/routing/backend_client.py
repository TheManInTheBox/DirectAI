"""
Backend client — async HTTP proxy to inference pods.

This module handles:
  - Forwarding requests to the correct backend service URL
  - Streaming SSE responses back to the client
  - Retries with exponential backoff on transient errors
  - Per-backend circuit breaker to avoid hammering failing pods
  - Cold-start detection for scale-to-zero backends
  - Correlation ID propagation
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
from opentelemetry.propagate import inject

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── Transient HTTP codes that should be retried ────────────────────
_RETRYABLE_STATUS = {502, 503, 504}
_MAX_RETRIES = 2
_RETRY_BACKOFF_BASE = 0.5  # seconds — exponential: 0.5, 1.0


class CircuitOpenError(Exception):
    """Raised when the circuit breaker for a backend is open."""

    def __init__(self, backend: str, reset_at: float) -> None:
        self.backend = backend
        self.reset_at = reset_at
        wait = max(0, reset_at - time.monotonic())
        super().__init__(f"Circuit open for {backend}, resets in {wait:.0f}s")


class _CircuitBreaker:
    """
    Simple per-backend circuit breaker.

    States:
      CLOSED   → requests pass through, failures counted
      OPEN     → requests rejected immediately (CircuitOpenError)
      HALF-OPEN → one probe request allowed; success → CLOSED, failure → OPEN

    Thresholds are intentionally low because GPU backends are expensive
    and cascading retries waste GPU time.
    """

    FAILURE_THRESHOLD = 5
    RESET_TIMEOUT = 30.0  # seconds in OPEN before trying HALF-OPEN

    def __init__(self) -> None:
        self._failures: int = 0
        self._state: str = "closed"  # closed | open | half-open
        self._opened_at: float = 0.0

    @property
    def is_open(self) -> bool:
        if self._state == "open":
            if time.monotonic() - self._opened_at >= self.RESET_TIMEOUT:
                self._state = "half-open"
                return False
            return True
        return False

    @property
    def reset_at(self) -> float:
        return self._opened_at + self.RESET_TIMEOUT

    def record_success(self) -> None:
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.FAILURE_THRESHOLD:
            self._state = "open"
            self._opened_at = time.monotonic()
            logger.warning(
                "Circuit OPEN after %d consecutive failures (reset in %.0fs)",
                self._failures,
                self.RESET_TIMEOUT,
            )


class BackendClient:
    """
    Async HTTP client for proxying requests to inference backends.

    Includes per-backend circuit breaker and retry with exponential backoff.
    Lifecycle managed by FastAPI lifespan — created once, closed on shutdown.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._circuits: dict[str, _CircuitBreaker] = {}

    def _circuit(self, url: str) -> _CircuitBreaker:
        """Get or create the circuit breaker keyed by backend host."""
        host = httpx.URL(url).host or url
        if host not in self._circuits:
            self._circuits[host] = _CircuitBreaker()
        return self._circuits[host]

    async def startup(self) -> None:
        settings = get_settings()
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=settings.backend_timeout,
                connect=settings.backend_connect_timeout,
            ),
            limits=httpx.Limits(
                max_connections=200,
                max_keepalive_connections=50,
            ),
            http2=True,
        )
        logger.info("Backend HTTP client started.")

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
            logger.info("Backend HTTP client closed.")

    async def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """
        Send a JSON POST to a backend with retry + circuit breaker.

        Does NOT raise on non-2xx — callers inspect status_code to
        distinguish backend validation errors (4xx) from failures (5xx).
        """
        cb = self._circuit(url)
        if cb.is_open:
            raise CircuitOpenError(url, cb.reset_at)

        headers = dict(headers or {})
        inject(headers)  # W3C traceparent propagation

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._client.post(
                    url, json=payload, headers=headers
                )
                if response.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                    logger.warning(
                        "Backend %s returned %d (attempt %d/%d), retrying...",
                        url, response.status_code, attempt + 1, _MAX_RETRIES + 1,
                    )
                    await asyncio.sleep(_RETRY_BACKOFF_BASE * (2 ** attempt))
                    continue
                if response.status_code >= 500:
                    cb.record_failure()
                else:
                    cb.record_success()
                return response
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                cb.record_failure()
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    logger.warning(
                        "Backend %s connect failed (attempt %d/%d): %s",
                        url, attempt + 1, _MAX_RETRIES + 1, exc,
                    )
                    await asyncio.sleep(_RETRY_BACKOFF_BASE * (2 ** attempt))
                    continue
                raise
            except httpx.TimeoutException:
                cb.record_failure()
                raise

        # Should be unreachable, but just in case
        if last_exc:
            raise last_exc
        return response  # type: ignore[possibly-undefined]

    async def post_stream(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> AsyncIterator[bytes]:
        """
        Send a JSON POST to a backend and yield SSE chunks.

        No retry on streaming — if the connection fails mid-stream,
        the client gets an error event. Circuit breaker still applies.
        """
        cb = self._circuit(url)
        if cb.is_open:
            raise CircuitOpenError(url, cb.reset_at)

        headers = dict(headers or {})
        inject(headers)  # W3C traceparent propagation

        try:
            async with self._client.stream(
                "POST",
                url,
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                cb.record_success()
                async for chunk in response.aiter_bytes():
                    yield chunk
        except (httpx.ConnectError, httpx.ConnectTimeout):
            cb.record_failure()
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                cb.record_failure()
            raise

    async def post_multipart(
        self,
        url: str,
        *,
        files: dict[str, Any],
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """
        Send a multipart/form-data POST (for audio transcription).

        Includes retry + circuit breaker (same as post_json).
        """
        cb = self._circuit(url)
        if cb.is_open:
            raise CircuitOpenError(url, cb.reset_at)

        headers = dict(headers or {})
        inject(headers)  # W3C traceparent propagation

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._client.post(
                    url,
                    files=files,
                    data=data or {},
                    headers=headers,
                )
                if response.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_BACKOFF_BASE * (2 ** attempt))
                    continue
                if response.status_code >= 500:
                    cb.record_failure()
                else:
                    cb.record_success()
                return response
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                cb.record_failure()
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_BACKOFF_BASE * (2 ** attempt))
                    continue
                raise

        if last_exc:
            raise last_exc
        return response  # type: ignore[possibly-undefined]
