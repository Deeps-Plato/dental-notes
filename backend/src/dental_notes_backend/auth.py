"""API key middleware — validates X-API-Key header on every request."""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from dental_notes_backend.config import settings

_OPEN_PATHS = {"/health", "/"}
_OPEN_PREFIXES = ("/static/",)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Reject requests missing or bearing a wrong X-API-Key header.

    The /health endpoint is intentionally left open so monitoring tools can
    reach it without credentials.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if path in _OPEN_PATHS or any(path.startswith(p) for p in _OPEN_PREFIXES):
            return await call_next(request)

        key = request.headers.get("X-API-Key", "")
        if not secrets.compare_digest(key, settings.dental_api_key):
            return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)

        return await call_next(request)
