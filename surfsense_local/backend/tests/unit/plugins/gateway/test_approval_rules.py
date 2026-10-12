import pytest

from modules.plugins.gateway.approval import needs_approval
from modules.plugins.gateway.ready_tool import ReadyTool
from modules.plugins.installed.models import PluginSource, ToolApproval, ToolExposure

pytestmark = pytest.mark.unit


def ready(
    source: PluginSource,
    approval: ToolApproval = ToolApproval.ASK,
    **annotations: bool,
) -> ReadyTool:
    """A tool as the gateway offers it, from `source`, with the given annotations."""
    return ReadyTool(
        qualified_name="notes__search",
        plugin_id="notes",
        plugin_name="Notes",
        plugin_source=source,
        tool="search",
        title=None,
        description="Search the notes.",
        input_schema={"type": "object"},
        annotations=annotations,
        approval=approval,
        exposure=ToolExposure.DIRECT,
    )


def test_a_first_party_read_only_tool_runs_without_asking() -> None:
    """SurfSense runs that server, so its read-only annotation is trusted."""
    assert needs_approval(ready(PluginSource.FIRST_PARTY, readOnlyHint=True)) is False


@pytest.mark.parametrize("source", [PluginSource.REGISTRY, PluginSource.CUSTOM])
def test_a_third_partys_read_only_tool_still_asks(source: PluginSource) -> None:
    """A server's read-only annotation is its own claim, trusted only from SurfSense's."""
    assert needs_approval(ready(source, readOnlyHint=True)) is True


def test_always_allow_skips_asking_for_a_tool_that_is_not_destructive() -> None:
    """Once the user sets Always allow, a safe tool runs without asking."""
    tool = ready(
        PluginSource.REGISTRY,
        ToolApproval.ALWAYS,
        readOnlyHint=False,
        destructiveHint=False,
    )

    assert needs_approval(tool) is False


def test_a_destructive_tool_asks_every_time_even_when_always_allowed() -> None:
    """Deleting or overwriting is confirmed on each call, whatever the setting."""
    tool = ready(PluginSource.FIRST_PARTY, ToolApproval.ALWAYS, destructiveHint=True)

    assert needs_approval(tool) is True


def test_a_tool_with_no_annotations_is_treated_as_destructive() -> None:
    """MCP's defaults: a tool that says nothing may write and may destroy."""
    assert needs_approval(ready(PluginSource.FIRST_PARTY, ToolApproval.ALWAYS)) is True
