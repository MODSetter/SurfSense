"""Which ready plugin tools a turn's agent holds when they do not all fit."""

import pytest

from modules.agent.tool_exposure.held_tools import Asked, held_tools
from modules.agent.tool_exposure.ranking import IndexedTool
from modules.agent.tool_exposure.tool_cost import tool_tokens
from modules.plugins.gateway.ready_tool import ReadyTool
from modules.plugins.installed.models import PluginSource, ToolApproval, ToolExposure

pytestmark = pytest.mark.unit


def _tool(plugin: str, name: str, description: str = "Does a thing.") -> IndexedTool:
    ready = ReadyTool(
        qualified_name=f"{plugin}__{name}",
        plugin_id=plugin,
        plugin_name=plugin.title(),
        plugin_source=PluginSource.CUSTOM,
        tool=name,
        title=None,
        description=description,
        input_schema={"type": "object", "properties": {}},
        annotations={},
        approval=ToolApproval.ASK,
        exposure=ToolExposure.DIRECT,
    )
    return IndexedTool(ready, plugin.title())


LINEAR = [
    _tool("linear", "create_issue", "Create an issue in a team's backlog."),
    _tool("linear", "list_projects", "List the workspace's projects."),
    _tool("linear", "add_comment", "Comment on an issue."),
]
GCAL = [
    _tool("gcal", "list_events", "List the calendar's events."),
    _tool("gcal", "create_event", "Create a calendar event."),
]
NOTES = [_tool("notes", f"tool_{n}", f"Note tool number {n}.") for n in range(6)]
EVERY = [*LINEAR, *GCAL, *NOTES]
ONE = tool_tokens(EVERY[0].ready)


def _held(asked: Asked, share: int, limit: int | None = None) -> set[str]:
    held = held_tools(EVERY, asked, share, limit, None)
    return {tool.qualified_name for tool in held.tools}


def test_when_every_tool_fits_every_tool_is_held() -> None:
    """Within the share, nothing is left to the catalogue."""
    held = held_tools(EVERY, Asked("hello"), 10**6, None, None)

    assert held.everything
    assert len(held.tools) == len(EVERY)


def test_past_the_share_the_tools_the_request_needs_are_held() -> None:
    """Retrieval fills the share with the tools the message ranks highest."""
    held = _held(Asked("create an issue for the login bug"), ONE * 2)

    assert "linear__create_issue" in held
    assert len(held) <= 2


def test_a_mentioned_plugin_is_held_whole_whatever_its_cost() -> None:
    """An @-mention is the user choosing it."""
    held = _held(Asked("look", mentioned=frozenset({"notes"})), ONE)

    assert {t.ready.qualified_name for t in NOTES} <= held


def test_a_plugin_the_message_names_is_held_by_its_best_tools() -> None:
    """The second app of a two-app request is what retrieval misses most."""
    held = _held(Asked("make an issue for each event in my Gcal"), ONE * 3)

    assert held & {"gcal__list_events", "gcal__create_event"}
    assert "linear__create_issue" in held


def test_tools_the_thread_used_stay_held() -> None:
    """A follow-up keeps the tools the thread was using, whatever it says."""
    held = _held(Asked("and again", used=frozenset({"notes_tool_4"})), ONE)

    assert "notes__tool_4" in held


def test_never_past_the_providers_limit() -> None:
    """Not even a mentioned plugin passes the provider's limit."""
    held = _held(Asked("look", mentioned=frozenset({"notes"})), 10**6, limit=4)

    assert len(held) == 4
