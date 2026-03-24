import pytest
from langchain_core.messages import AIMessage

from app.agents.new_chat.middleware.dedup_tool_calls import (
    DedupHITLToolCallsMiddleware,
)

pytestmark = pytest.mark.unit


def _make_state(tool_calls: list[dict]) -> dict:
    """Build a minimal agent state with one AIMessage carrying *tool_calls*."""
    msg = AIMessage(content="", tool_calls=tool_calls)
    return {"messages": [msg]}


def test_duplicate_hitl_calls_reduced_to_first():
    """When the LLM emits the same HITL tool call twice, only the first is kept."""
    mw = DedupHITLToolCallsMiddleware()

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
