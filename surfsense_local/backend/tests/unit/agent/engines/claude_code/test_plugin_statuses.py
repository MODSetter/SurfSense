"""A plugin is reported unavailable only from Claude Code's settled answer for the turn."""

import pytest

from modules.agent.engines.claude_code.plugin_statuses import unavailable_plugins
from modules.agent.plugin_tools.turn_plugins import TurnPlugin
from modules.agent.plugin_tools.unavailable_plugin import UnavailablePlugin

pytestmark = pytest.mark.unit


def _plugin(name: str, title: str, *, licensed: bool = False) -> TurnPlugin:
    return TurnPlugin(
        name=name,
        title=title,
        url=f"https://{name}.example/mcp",
        headers={},
        licensed=licensed,
    )


PLUGINS = [
    _plugin("google-search", "Google Search", licensed=True),
    _plugin("deepwiki", "DeepWiki"),
    _plugin("notion", "Notion"),
]


def _servers(**statuses: str) -> list[dict]:
    return [{"name": name, "status": status} for name, status in statuses.items()]


def test_connected_plugins_are_not_reported() -> None:
    """The false alarm: a plugin still connecting at start is connected by the turn."""
    servers = _servers(
        surfsense="connected", **{"google-search": "connected"}, deepwiki="connected"
    )

    assert unavailable_plugins(servers, PLUGINS) == []


def test_each_settled_failure_says_what_to_do() -> None:
    """Named as opencode's turn names them: unreachable, or a sign-in, or the license."""
    servers = _servers(
        **{"google-search": "needs-auth"}, deepwiki="failed", notion="needs-auth"
    )

    assert unavailable_plugins(servers, PLUGINS) == [
        UnavailablePlugin("Google Search", "license"),
        UnavailablePlugin("DeepWiki", "unreachable"),
        UnavailablePlugin("Notion", "sign_in"),
    ]


def test_a_plugin_still_connecting_when_the_turn_began_is_unreachable() -> None:
    """Claude Code waits its MCP timeout before a turn; past it, as opencode's add times out."""
    assert unavailable_plugins(_servers(deepwiki="pending"), PLUGINS) == [
        UnavailablePlugin("DeepWiki", "unreachable")
    ]


def test_surfsenses_own_tools_are_never_reported_as_a_plugin() -> None:
    """Its tool endpoint is no plugin; a failure there is not the user's to fix."""
    assert unavailable_plugins(_servers(surfsense="failed"), PLUGINS) == []
