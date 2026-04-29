import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from app.agents.new_chat.middleware.dedup_tool_calls import (
    DedupHITLToolCallsMiddleware,
    wrap_dedup_key_by_arg_name,
)

pytestmark = pytest.mark.unit


def _make_state(tool_calls: list[dict]) -> dict:
    """Build a minimal agent state with one AIMessage carrying *tool_calls*."""
    msg = AIMessage(content="", tool_calls=tool_calls)
    return {"messages": [msg]}


def _hitl_tool(name: str, *, dedup_arg: str) -> StructuredTool:
    """Build a tool with declarative ``dedup_key`` metadata.

    Mirrors the ``ToolDefinition.dedup_key`` -> ``tool.metadata["dedup_key"]``
    propagation done by :func:`build_tools` after the cleanup tier.
    """

    def _fn(**kwargs):
        return "ok"

    return StructuredTool.from_function(
        func=_fn,
        name=name,
        description="x",
        metadata={"dedup_key": wrap_dedup_key_by_arg_name(dedup_arg)},
    )


def test_duplicate_hitl_calls_reduced_to_first():
    """When the LLM emits the same HITL tool call twice, only the first is kept.

    After the cleanup tier removed ``_NATIVE_HITL_TOOL_DEDUP_KEYS``, the
    resolver is sourced from ``ToolDefinition.dedup_key`` propagated onto
    ``tool.metadata`` — which the registry does at agent build time. The
    test mirrors that wiring with an in-memory tool.
    """
    tool = _hitl_tool("delete_calendar_event", dedup_arg="event_title_or_id")
    mw = DedupHITLToolCallsMiddleware(agent_tools=[tool])

    state = _make_state(
        [
            {
                "id": "call_1",
                "name": "delete_calendar_event",
                "args": {"event_title_or_id": "Doctor Appointment"},
            },
            {
                "id": "call_2",
                "name": "delete_calendar_event",
                "args": {"event_title_or_id": "Doctor Appointment"},
            },
        ]
    )

    result = mw.after_model(state, runtime=None)  # type: ignore[arg-type]

    assert result is not None, "Expected middleware to return updated state"
    updated_calls = result["messages"][0].tool_calls
    assert len(updated_calls) == 1
    assert updated_calls[0]["id"] == "call_1"
