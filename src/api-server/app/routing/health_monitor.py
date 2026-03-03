"""
Backend health monitor — periodic health checks for inference backends.

Runs as a background task during API server lifetime. Pings each backend's
/healthz endpoint and tracks status. Used by /readyz to report aggregate
health and by route handlers to fast-fail requests to known-down backends.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_PROBE_INTERVAL = 10.0  # seconds between health checks
_PROBE_TIMEOUT = 3.0  # per-backend timeout


@dataclass
class BackendStatus:
    """Health status of a single inference backend."""

    healthy: bool = False
    last_check: float = 0.0
    last_error: str = ""
    consecutive_failures: int = 0


class BackendHealthMonitor:
    """
    Periodically probes inference backends and exposes health status.

    Usage:
        monitor = BackendHealthMonitor()
        await monitor.start(backends)
        ...
        status = monitor.get_status("llama-3-1-70b-instruct")
        ...
        await monitor.stop()
    """

    def __init__(self) -> None:
        self._statuses: dict[str, BackendStatus] = {}
        self._task: asyncio.Task | None = None
        self._backends: dict[str, str] = {}  # name → healthz URL
        self._client: httpx.AsyncClient | None = None

    async def start(self, backends: dict[str, str]) -> None:
        """
        Start background health checks.

        Args:
            backends: mapping of model name → backend base URL
                      e.g. {"llama-70b": "http://llama-70b.directai.svc:8001"}
        """
        self._backends = {
            name: f"{url.rstrip('/')}/healthz" for name, url in backends.items()
        }
        self._statuses = {name: BackendStatus() for name in backends}
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout=_PROBE_TIMEOUT, connect=2.0),
        )
        # Run first check immediately so health data is available at startup
        await self._check_all()
        self._task = asyncio.create_task(self._run(), name="backend-health-monitor")
        logger.info("Backend health monitor started for %d backends", len(backends))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._client:
            await self._client.aclose()
        logger.info("Backend health monitor stopped.")

    async def _run(self) -> None:
        while True:
            try:
                await self._check_all()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("Unexpected error in health monitor loop")
            await asyncio.sleep(_PROBE_INTERVAL)

    async def _check_all(self) -> None:
        tasks = [
            self._check_one(name, url)
            for name, url in self._backends.items()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_one(self, name: str, url: str) -> None:
        status = self._statuses[name]
        try:
            resp = await self._client.get(url)
            if resp.status_code < 400:
                status.healthy = True
                status.last_error = ""
                status.consecutive_failures = 0
            else:
                status.healthy = False
                status.last_error = f"HTTP {resp.status_code}"
                status.consecutive_failures += 1
        except Exception as exc:
            status.healthy = False
            status.last_error = str(exc)[:200]
            status.consecutive_failures += 1
        status.last_check = time.monotonic()

    def get_status(self, name: str) -> BackendStatus | None:
        return self._statuses.get(name)

    def any_healthy(self) -> bool:
        """Return True if at least one backend is healthy."""
        if not self._statuses:
            return False
        return any(s.healthy for s in self._statuses.values())

    def all_healthy(self) -> bool:
        if not self._statuses:
            return False
        return all(s.healthy for s in self._statuses.values())

    def summary(self) -> dict[str, bool]:
        """Return {name: healthy} mapping for readyz reporting."""
        return {name: s.healthy for name, s in self._statuses.items()}
