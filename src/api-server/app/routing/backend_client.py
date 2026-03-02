"""
Backend client — async HTTP proxy to inference pods.

This module handles:
  - Forwarding requests to the correct backend service URL
  - Streaming SSE responses back to the client
  - Timeouts, retries (future), and error translation
  - Correlation ID propagation
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class BackendClient:
    """
    Async HTTP client for proxying requests to inference backends.

    Lifecycle managed by FastAPI lifespan — created once, closed on shutdown.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

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
        Send a JSON POST to a backend and return the full response.

        Raises httpx.HTTPStatusError on 4xx/5xx from backend.
        """
        response = await self._client.post(url, json=payload, headers=headers or {})
        response.raise_for_status()
        return response

    async def post_stream(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> AsyncIterator[bytes]:
        """
        Send a JSON POST to a backend and yield SSE chunks.

        Yields raw bytes — the caller is responsible for framing as
        text/event-stream to the client.
        """
        async with self._client.stream(
            "POST",
            url,
            json=payload,
            headers=headers or {},
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk

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
        """
        response = await self._client.post(
            url,
            files=files,
            data=data or {},
            headers=headers or {},
        )
        response.raise_for_status()
        return response
