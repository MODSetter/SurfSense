"""Wrap the SDK's MCP endpoint with identity + CORS for the remote transport.

CORS is outermost so keyless browser preflight is answered before the identity
middleware. ``/health`` is a public path, exempt from the key check.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from ..auth.middleware import ApiKeyIdentityMiddleware

HEALTH_PATH = "/health"


async def _health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def build_http_app(mcp: FastMCP) -> ASGIApp:
    """Return the MCP streamable-http app wrapped with identity + CORS."""
    mcp.custom_route(HEALTH_PATH, methods=["GET"])(_health)
    app: ASGIApp = ApiKeyIdentityMiddleware(
        mcp.streamable_http_app(), public_paths={HEALTH_PATH}
    )
    return CORSMiddleware(
        app,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
