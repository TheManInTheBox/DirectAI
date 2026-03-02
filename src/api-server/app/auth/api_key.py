"""
API key authentication.

MVP: validates against a static set from environment variable.
Production: swap for Key Vault–backed async lookup (same interface).
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
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

    if credentials.credentials not in settings.api_key_set:
        logger.warning("Invalid API key attempted: %s...", credentials.credentials[:8])
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials
