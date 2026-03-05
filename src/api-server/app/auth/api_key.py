"""
API key authentication — DB-first with env-var fallback.

Resolution order:
  1. If ``PostgresKeyStore`` is wired into ``app.state.key_store`` and
     enabled, SHA-256 the bearer token and look it up in the ``api_keys``
     table.  Returns ``KeyInfo`` (key_id, user_id, name).
  2. If the DB store is disabled or returns nothing, fall back to the
     static ``DIRECTAI_API_KEYS`` env var (dev/test mode).
  3. If both miss, return 401.

SECURITY: constant-time comparison for the env-var path.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


def _constant_time_key_check(candidate: str, valid_keys: set[str]) -> bool:
    """
    Check if candidate matches any valid key using constant-time comparison.

    Iterates ALL keys regardless of match to avoid leaking which key
    (or even whether any key) matched via timing.
    """
    matched = False
    for key in valid_keys:
        if hmac.compare_digest(candidate.encode("utf-8"), key.encode("utf-8")):
            matched = True
    return matched


async def require_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),  # noqa: B008
) -> str:
    """
    FastAPI dependency — extracts and validates the Bearer token.

    Returns the API key string on success.  Stashes ``KeyInfo`` (user_id,
    key_id) on ``request.state.key_info`` when resolved via DB.
    Raises 401 if auth is enabled and the key is missing or invalid.
    Passes through silently if auth is disabled (dev mode).
    """
    settings = get_settings()

    if not settings.auth_enabled:
        return "dev-no-auth"

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide a Bearer token in the Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # ── 1. Try PostgreSQL key store ─────────────────────────────
    key_store = getattr(request.app.state, "key_store", None)
    if key_store is not None and key_store.enabled:
        key_info = await key_store.validate(token)
        if key_info is not None:
            # Stash for usage metering in route handlers
            request.state.key_info = key_info
            return token

    # ── 2. Fall back to env-var static keys ─────────────────────
    if settings.api_key_set and _constant_time_key_check(token, settings.api_key_set):
        return token

    # ── 3. Both missed → reject ─────────────────────────────────
    key_hash = hashlib.sha256(token.encode()).hexdigest()[:12]
    logger.warning("Invalid API key attempted (sha256:%s)", key_hash)
    raise HTTPException(
        status_code=401,
        detail="Invalid API key.",
        headers={"WWW-Authenticate": "Bearer"},
    )
