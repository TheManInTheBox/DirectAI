"""
Correlation ID middleware.

Injects a unique request ID into every request. If the client sends
X-Request-ID, it's reused; otherwise a new UUID is generated.

The ID is:
  - Added to the request state (available to route handlers)
  - Propagated to backend requests via X-Request-ID header
  - Returned to the client in the X-Request-ID response header
  - Included in structured log context
"""

from __future__ import annotations

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_MAX_ID_LENGTH = 128
_SAFE_PATTERN = re.compile(r"[^a-zA-Z0-9\-_.]")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw_id = request.headers.get("x-request-id") or ""
        if raw_id:
            # Strip unsafe characters and truncate
            request_id = _SAFE_PATTERN.sub("", raw_id)[:_MAX_ID_LENGTH]
        if not raw_id or not request_id:
            request_id = uuid.uuid4().hex
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
