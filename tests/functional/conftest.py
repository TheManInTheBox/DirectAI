"""Shared fixtures for functional tests against the live dev/shared environment."""

from __future__ import annotations

import os
import time

import httpx
import pytest

# ── Endpoints ───────────────────────────────────────────────
API_BASE_URL = os.getenv("DIRECTAI_FUNC_TEST_BASE_URL", "https://api.agilecloud.ai")
WEB_BASE_URL = os.getenv("DIRECTAI_FUNC_TEST_WEB_URL", "https://agilecloud.ai")
API_KEY = os.getenv("DIRECTAI_FUNC_TEST_KEY", "")

# Delay between API calls to stay under the live 60 RPM rate limit.
_INTER_TEST_DELAY = float(os.getenv("DIRECTAI_FUNC_TEST_DELAY", "1.5"))


# ── HTTP Clients ────────────────────────────────────────────
@pytest.fixture(scope="session")
def api_client() -> httpx.Client:
    """Authenticated httpx client for the API server.

    Skips the calling test if DIRECTAI_FUNC_TEST_KEY is not set.
    """
    if not API_KEY:
        pytest.skip("DIRECTAI_FUNC_TEST_KEY not set")
    client = httpx.Client(
        base_url=API_BASE_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        verify=False,  # dev certs may be self-signed
        timeout=httpx.Timeout(timeout=60.0, connect=10.0),
    )
    yield client
    client.close()


@pytest.fixture(scope="session")
def anon_client() -> httpx.Client:
    """Unauthenticated httpx client for the API server."""
    client = httpx.Client(
        base_url=API_BASE_URL,
        verify=False,
        timeout=httpx.Timeout(timeout=30.0, connect=10.0),
    )
    yield client
    client.close()


@pytest.fixture(scope="session")
def web_client() -> httpx.Client:
    """httpx client for the web frontend."""
    client = httpx.Client(
        base_url=WEB_BASE_URL,
        verify=False,
        timeout=httpx.Timeout(timeout=30.0, connect=10.0),
        follow_redirects=True,
    )
    yield client
    client.close()


# ── Rate-limit pacer ────────────────────────────────────────
@pytest.fixture(autouse=True)
def _pace_api_calls(request: pytest.FixtureRequest) -> None:
    """Sleep between tests that hit the live API to stay under 60 RPM."""
    yield
    # Only pace tests that actually use api_client or anon_client
    module = request.node.module.__name__  # type: ignore[union-attr]
    if "test_web" not in module:
        time.sleep(_INTER_TEST_DELAY)
