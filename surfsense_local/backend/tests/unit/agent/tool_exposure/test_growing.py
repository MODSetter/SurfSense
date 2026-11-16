"""A turn's holding grows by whole plugins, and opencode is told before the step that needs it."""

import pytest

from modules.agent.plugin_tools.turn_plugins import TurnPlugin
from modules.agent.tool_exposure.growing import (
    grow_after_call,
    grow_by_search,
    hold_plugins,
)
from modules.agent.tool_exposure.held_tools import Asked
from modules.agent.tool_exposure.holdings import Holding
from modules.agent.tool_exposure.ranking import IndexedTool
from modules.plugins.gateway.ready_tool import ReadyTool
from modules.plugins.installed.models import PluginSource, ToolApproval, ToolExposure

pytestmark = pytest.mark.unit


class _Opencode:
    def __init__(self) -> None:
        self.written: list[list[dict[str, str]]] = []

    async def set_session_rules(self, session_id: str, rules: list[dict]) -> None:
        self.written.append(rules)


def _indexed(plugin: str, tool: str, description: str) -> IndexedTool:
    ready = ReadyTool(
        qualified_name=f"{plugin}__{tool}",
        plugin_id=plugin,
        plugin_name=plugin.title(),
        plugin_source=PluginSource.CUSTOM,
        tool=tool,
        title=None,
        description=description,
        input_schema={"type": "object", "properties": {}},
        annotations={},
        approval=ToolApproval.ASK,
        exposure=ToolExposure.DIRECT,
    )
    return IndexedTool(ready, plugin.title())


TOOLS = [
    _indexed("linear", "create_issue", "Create an issue."),
    _indexed("linear", "add_comment", "Comment on an issue."),
    _indexed("gcal", "list_events", "List the calendar's events."),
    _indexed("gcal", "create_event", "Create a calendar event."),
]


def _plugin(name: str, tools: list[str]) -> TurnPlugin:
    return TurnPlugin(
        name=name,
        title=name.title(),
        url="",
        headers={},
        rules={f"{name}_{tool}": "allow" for tool in tools},
    )


def _holding(held: set[str], limit: int | None = None) -> Holding:
    return Holding(
        session_id="ses_1",
        plugins=[
            _plugin("linear", ["create_issue", "add_comment"]),
            _plugin("gcal", ["list_events", "create_event"]),
        ],
        servers={"linear", "gcal"},
        held=held,
        tools=TOOLS,
        asked=Asked("plan the week"),
        limit=limit,
    )


async def test_a_plugin_is_held_whole_and_opencode_told_at_once() -> None:
    """Every tool of the plugin, in one write of the session's rules."""
    opencode, holding = _Opencode(), _holding({"linear_create_issue"})

    added = await hold_plugins(opencode, holding, ["gcal"])

    assert added == {"gcal_list_events", "gcal_create_event"}
    (rules,) = opencode.written
    allowed = {r["permission"] for r in rules if r["action"] != "deny"}
    assert allowed == {"linear_create_issue", "gcal_list_events", "gcal_create_event"}


async def test_after_a_call_its_plugins_other_tools_are_held_and_no_other_plugin() -> (
    None
):
    """Once the agent is in the right plugin, the next tool is most often a sibling.

    Guessing another plugin from the call was right about one time in four, and
    after every call of a one-app request it loaded one nothing needed.
    """
    opencode, holding = _Opencode(), _holding({"linear_create_issue"})

    added = await grow_after_call(opencode, holding, "linear")

    assert added == {"linear_add_comment"}


async def test_a_call_never_holds_another_plugin_however_it_ranks() -> None:
    """The calendar ranks first for the request; the agent reaches it through the
    catalogue or by asking, not by a guess after each call."""
    opencode = _Opencode()
    holding = _holding({"linear_create_issue", "linear_add_comment"})
    holding.asked = Asked("plan the week's calendar events")

    added = await grow_after_call(opencode, holding, "linear")

    assert added == set()
    assert opencode.written == []


async def test_a_search_holds_the_plugin_of_its_best_tool() -> None:
    """The best tool not held brings its whole plugin."""
    opencode, holding = _Opencode(), _holding({"linear_create_issue"})

    added = await grow_by_search(opencode, holding, "calendar events", None)

    assert added == {"gcal_list_events", "gcal_create_event"}


async def test_nothing_new_writes_nothing() -> None:
    """A plugin already held leaves the rules, and the model's cached prompt, alone."""
    opencode = _Opencode()
    holding = _holding({"linear_create_issue", "linear_add_comment"})

    assert await hold_plugins(opencode, holding, ["linear"]) == set()
    assert opencode.written == []


async def test_a_holding_never_passes_the_providers_limit() -> None:
    """Past the provider's limit on tools, the rest of the plugin stays out."""
    opencode, holding = _Opencode(), _holding({"linear_create_issue"}, limit=2)

    added = await hold_plugins(opencode, holding, ["gcal"])

    assert len(holding.held) == 2
    assert len(added) == 1
