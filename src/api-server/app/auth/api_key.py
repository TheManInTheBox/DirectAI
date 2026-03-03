"""
API key authentication.

MVP: validates against a static set from environment variable.
Production: swap for Key Vault–backed async lookup (same interface).

SECURITY: Uses hmac.compare_digest for constant-time comparison to
prevent timing side-channel attacks on API key validation.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import HTTPException, Security
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
        # Do NOT early-return — must compare against every key.
    return matched


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),  # noqa: B008
) -> str:
    """
    FastAPI dependency — extracts and validates the Bearer token.

    Returns the API key string on success.
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

    if not _constant_time_key_check(credentials.credentials, settings.api_key_set):
        key_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()[:12]
        logger.warning("Invalid API key attempted (sha256:%s)", key_hash)
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials
