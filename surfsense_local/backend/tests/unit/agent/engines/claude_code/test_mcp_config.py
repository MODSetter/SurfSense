"""The MCP servers a turn gives Claude Code, in a file only the user can read."""

import json
import os
import sys
from pathlib import Path

import pytest

from modules.agent.engines.claude_code.mcp_config import write_mcp_config

pytestmark = pytest.mark.unit
SERVERS = {
    "notion": {
        "type": "http",
        "url": "https://mcp.notion.example/mcp",
        "headers": {"Authorization": "Bearer token"},
    }
}


def test_the_servers_and_their_headers_are_written_for_claude_code(
    tmp_path: Path,
) -> None:
    """As Claude Code's --mcp-config reads them; the SDK would put a dict on its command line."""
    path = write_mcp_config(tmp_path / "claude", SERVERS)

    assert json.loads(path.read_text()) == {"mcpServers": SERVERS}


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_no_other_user_can_read_the_file(tmp_path: Path) -> None:
    """It holds sign-in headers."""
    path = write_mcp_config(tmp_path / "claude", SERVERS)

    assert os.stat(path).st_mode & 0o077 == 0
    assert os.stat(path.parent).st_mode & 0o077 == 0


def test_two_turns_never_share_a_file(tmp_path: Path) -> None:
    """Each client removes its own when it closes."""
    first = write_mcp_config(tmp_path, SERVERS)
    second = write_mcp_config(tmp_path, SERVERS)

    assert first != second
