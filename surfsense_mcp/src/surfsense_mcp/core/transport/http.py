"""Assemble the streamable-http ASGI app for the remote transport.

Wraps the SDK's MCP endpoint with the API-key identity middleware and CORS.
CORS sits outermost so browser preflight (which carries no key) is answered
before the identity middleware, and clients can read the ``Mcp-Session-Id``
header the streamable-http protocol relies on.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from ..auth.middleware import ApiKeyIdentityMiddleware


def build_http_app(mcp: FastMCP) -> ASGIApp:
    """Return the MCP streamable-http app wrapped with identity + CORS."""
    app: ASGIApp = ApiKeyIdentityMiddleware(mcp.streamable_http_app())
    return CORSMiddleware(
        app,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
