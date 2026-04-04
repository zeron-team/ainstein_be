# app/core/request_id.py
"""
Request ID middleware — generates a unique ID per request for traceability.

Usage:
  - Automatically adds X-Request-ID header to all responses
  - Access the current request ID in any code via: get_request_id()
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable: accessible from any async/sync code in the request lifecycle
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the current request's ID (empty string if called outside a request)."""
    return _request_id_ctx.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Assigns a UUID4 to each incoming request.

    - If the client sends X-Request-ID, it is reused (useful for distributed tracing).
    - Otherwise a new one is generated.
    - The ID is set in a ContextVar for use in logging and is returned in the response header.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = _request_id_ctx.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            _request_id_ctx.reset(token)
