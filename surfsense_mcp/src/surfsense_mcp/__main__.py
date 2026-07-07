"""Entry point: load settings from the environment and run the MCP server.

Defaults to stdio (what Cursor, Claude Code, and Claude Desktop launch). stdout
is the protocol channel, so every log line goes to stderr.
"""

from __future__ import annotations

import logging
import os
import sys

from .config import Settings
from .server import build_server


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    mcp, _client = build_server(settings)

    transport = os.environ.get("SURFSENSE_MCP_TRANSPORT", "stdio").strip() or "stdio"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
