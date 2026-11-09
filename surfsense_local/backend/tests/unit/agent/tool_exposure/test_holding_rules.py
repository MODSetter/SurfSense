"""The session's rules a holding writes: every plugin tool denied, then the held ones allowed."""

import pytest

from modules.agent.plugin_tools.turn_plugins import TurnPlugin
from modules.agent.tool_exposure.holdings import Holding

pytestmark = pytest.mark.unit


def test_every_held_server_is_denied_then_the_held_tools_allowed() -> None:
    """Set whole each time, so no earlier turn's allow survives a tool switched off."""
    plugin = TurnPlugin(
        name="a",
        title="A",
        url="",
        headers={},
        rules={"a_search": "allow", "a_delete": "ask", "a_other": "allow"},
    )
    holding = Holding(
        session_id="ses_1",
        plugins=[plugin],
        servers={"gone", "surfsense", "a"},
        held={"a_search", "a_delete"},
    )

    rules = holding.rules()

    assert sorted(r["permission"] for r in rules if r["action"] == "deny") == [
        "a_*",
        "gone_*",
    ]
    assert [r for r in rules if r["action"] != "deny"] == [
        {"permission": "a_search", "pattern": "*", "action": "allow"},
        {"permission": "a_delete", "pattern": "*", "action": "ask"},
    ]
