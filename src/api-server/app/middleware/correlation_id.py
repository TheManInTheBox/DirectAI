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

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
