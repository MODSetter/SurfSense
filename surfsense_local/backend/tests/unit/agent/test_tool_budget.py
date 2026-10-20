import pytest

from modules.agent.plugin_tools.tool_budget import offered_tools, tool_tokens
from modules.plugins.gateway.ready_tool import ReadyTool
from modules.plugins.installed.models import PluginSource, ToolApproval, ToolExposure

pytestmark = pytest.mark.unit


def ready(
    plugin: str, *tools: str, description: str = "Does a thing."
) -> list[ReadyTool]:
    """A plugin's ready tools, in its server's order."""
    return [
        ReadyTool(
            qualified_name=f"{plugin}_{tool}",
            plugin_id=plugin,
            plugin_name=plugin.title(),
            plugin_source=PluginSource.CUSTOM,
            tool=tool,
            title=None,
            description=description,
            input_schema={},
            annotations={},
            approval=ToolApproval.ASK,
            exposure=ToolExposure.DIRECT,
        )
        for tool in tools
    ]


def names(tools: list[ReadyTool]) -> list[str]:
    """As the runtime names them."""
    return [tool.qualified_name for tool in tools]


def test_without_a_budget_every_ready_tool_is_offered() -> None:
    """A runtime with its own tool search gets them all."""
    tools = ready("notion", *[f"t{n}" for n in range(40)])

    assert offered_tools(tools, frozenset(), None) == tools


def test_plugins_take_turns_so_a_big_one_cannot_crowd_out_the_rest() -> None:
    """Connected first, Notion would take the whole budget; each plugin gets a tool first."""
    tools = ready("notion", "a", "b", "c", "d") + ready("context7", "r", "q")
    budget = tool_tokens(tools[0]) * 3

    offered = names(offered_tools(tools, frozenset(), budget))

    assert offered == ["notion_a", "notion_b", "context7_r"]


def test_a_mentioned_plugins_tools_all_come_first_past_the_budget() -> None:
    """The user chose it; the other plugins share what is left."""
    tools = ready("notion", "a", "b") + ready("context7", "r", "q")
    budget = tool_tokens(tools[0]) * 3

    offered = names(offered_tools(tools, frozenset({"context7"}), budget))

    assert offered == ["notion_a", "context7_r", "context7_q"]


def test_a_tool_too_big_for_what_is_left_leaves_room_for_smaller_ones() -> None:
    """A plugin whose next tool does not fit stops; another's smaller one still goes in."""
    big = ready("wiki", "read", description="x" * 4000)
    small = ready("notes", "search")
    budget = tool_tokens(small[0]) * 2

    offered = names(offered_tools(big + small, frozenset(), budget))

    assert offered == ["notes_search"]
