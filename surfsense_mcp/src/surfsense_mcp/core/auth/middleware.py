"""ASGI middleware that establishes the caller's identity for each request.

A pure ASGI middleware, deliberately not Starlette's ``BaseHTTPMiddleware``:
the latter runs the endpoint in a separate task, so a contextvar set in it does
not reach the tool handler. A pure middleware sets the key in the request's own
task, from which the SDK's per-request handling inherits it (verified).

Requests without a key are rejected here so no tool ever runs unauthenticated.
"""

from __future__ import annotations

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .headers import extract_api_key
from .identity import bind_api_key, unbind_api_key


class ApiKeyIdentityMiddleware:
    """Binds the per-request API key into the identity contextvar, or 401s."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        api_key = extract_api_key(Headers(scope=scope))
        if api_key is None:
            await _unauthenticated()(scope, receive, send)
            return

        token = bind_api_key(api_key)
        try:
            await self._app(scope, receive, send)
        finally:
            unbind_api_key(token)


def _unauthenticated() -> JSONResponse:
    return JSONResponse(
        {
            "error": "unauthorized",
            "message": (
                "Missing SurfSense API key. Send 'Authorization: Bearer "
                "ss_pat_...' (or an X-API-Key header)."
            ),
        },
        status_code=401,
    )
