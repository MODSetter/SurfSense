from pathlib import Path

import pytest

from modules.agent.plugin_tools.give_plugins import UnavailablePlugin, give_plugins
from modules.agent.plugin_tools.turn_plugins import TurnPlugin

pytestmark = pytest.mark.unit


class Opencode:
    """opencode's MCP endpoints, answering every server added as needing sign-in."""

    async def tool_servers(self, folder: Path) -> dict[str, str]:
        return {}

    async def drop_tool_server(self, folder: Path, name: str) -> None:
        return None

    async def add_tool_server(self, folder, name, url, headers, timeout_seconds):
        return "needs_auth"

    async def set_session_rules(self, folder, session_id, rules) -> None:
        return None


async def test_a_refused_license_is_named_as_one_not_as_a_sign_in(
    tmp_path: Path,
) -> None:
    """A paid plugin's refusal is its license; signing in again would not help."""
    plugins = [
        TurnPlugin(
            "amazon", "Amazon", "https://plugins.example/amazon/mcp", {}, licensed=True
        ),
        TurnPlugin("notion", "Notion", "https://mcp.notion.example/mcp", {}),
    ]

    unavailable = await give_plugins(Opencode(), tmp_path, "s-1", plugins)  # type: ignore[arg-type]

    assert unavailable == [
        UnavailablePlugin("Amazon", "license"),
        UnavailablePlugin("Notion", "sign_in"),
    ]
