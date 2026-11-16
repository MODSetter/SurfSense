"""The MCP servers given to Claude Code, written where only the user can read them.

Passed as a dict, the SDK puts them on Claude Code's command line, where any
process on the machine can read the sign-in headers.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_mcp_config(directory: Path, servers: dict[str, Any]) -> Path:
    """A new file for one client; the caller removes it when the client closes."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    # mkstemp makes the file 0600 and never reuses a name.
    descriptor, name = tempfile.mkstemp(prefix="mcp-", suffix=".json", dir=directory)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        json.dump({"mcpServers": servers}, file)
    return Path(name)
