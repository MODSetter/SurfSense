"""Transport wiring for the MCP server (streamable-http app assembly)."""

from .http import build_http_app

__all__ = ["build_http_app"]
