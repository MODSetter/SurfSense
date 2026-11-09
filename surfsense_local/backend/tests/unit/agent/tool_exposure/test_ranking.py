"""Ranking a plugin's tools against what the user asked, by keyword and by meaning."""

import pytest

from modules.agent.tool_exposure.ranking import IndexedTool, ranked
from modules.plugins.gateway.ready_tool import ReadyTool
from modules.plugins.installed.models import PluginSource, ToolApproval, ToolExposure

pytestmark = pytest.mark.unit


def _tool(plugin: str, name: str, description: str) -> IndexedTool:
    ready = ReadyTool(
        qualified_name=f"{plugin}__{name}",
        plugin_id=plugin,
        plugin_name=plugin.title(),
        plugin_source=PluginSource.CUSTOM,
        tool=name,
        title=None,
        description=description,
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        annotations={},
        approval=ToolApproval.ASK,
        exposure=ToolExposure.DIRECT,
    )
    return IndexedTool(ready, f"{plugin.title()}: a {plugin} plugin")


TOOLS = [
    _tool("linear", "create_issue", "Create an issue in a team's backlog."),
    _tool("linear", "list_projects", "List the workspace's projects."),
    _tool("hubspot", "search_objects", "Search CRM objects by property."),
    _tool("gcal", "list_events", "List the events in a calendar between two times."),
]


def _names(tools: list[IndexedTool]) -> list[str]:
    return [t.ready.tool for t in tools]


def test_words_the_message_shares_with_a_tool_rank_it_first() -> None:
    """A word of the request in a tool's name or description."""
    assert _names(ranked(TOOLS, "file an issue for the login bug", None))[0] == (
        "create_issue"
    )


def test_meaning_and_keywords_are_fused_by_rank() -> None:
    """A tool the embedder alone ranks first still ranks high, without a weighting."""

    class Embed:
        """ "agenda" means the calendar; no word of the request says so."""

        def query(self, text: str) -> list[float]:
            return self._vector(text)

        def documents(self, texts: list[str]) -> list[list[float]]:
            return [self._vector(text) for text in texts]

        def _vector(self, text: str) -> list[float]:
            near = "calendar" in text or "agenda" in text
            return [1.0, 0.0] if near else [0.0, 1.0]

    order = _names(ranked(TOOLS, "what is on my agenda", Embed()))

    assert order[0] == "list_events"


def test_a_message_matching_nothing_keeps_every_tool() -> None:
    """Nothing to rank by: the order given."""
    assert sorted(_names(ranked(TOOLS, "", None))) == sorted(_names(TOOLS))
