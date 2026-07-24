"""Entry point: load settings from the environment and run the MCP server.

Two transports share one build:
- ``stdio`` (default): Cursor/Claude launch one process per user; the key comes
  from the environment, so it is required here.
- ``streamable-http``: one process serves many users, each passing their own key
  per request; the key is enforced by the transport's auth middleware instead.

For stdio, stdout is the protocol channel, so every log line goes to stderr.
"""

from __future__ import annotations

import logging
import os
import sys

from mcp.server.fastmcp import FastMCP

from .config import Settings
from .server import build_server


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    transport = os.environ.get("SURFSENSE_MCP_TRANSPORT", "stdio").strip() or "stdio"
    mcp, _client = build_server(settings)

    if transport in ("streamable-http", "http"):
        _run_http(mcp, settings)
        return

    if transport == "stdio" and not settings.api_key:
        raise SystemExit(
            "SURFSENSE_API_KEY is required for stdio transport. Create an API "
            "key in SurfSense (Settings -> API) and pass it via the "
            "SURFSENSE_API_KEY environment variable."
        )
    mcp.run(transport=transport)


def _run_http(mcp: FastMCP, settings: Settings) -> None:
    """Serve the streamable-http app directly, so the per-request identity
    middleware wraps the SDK's MCP endpoint."""
    import uvicorn

    from .core.transport import build_http_app

    uvicorn.run(build_http_app(mcp), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
