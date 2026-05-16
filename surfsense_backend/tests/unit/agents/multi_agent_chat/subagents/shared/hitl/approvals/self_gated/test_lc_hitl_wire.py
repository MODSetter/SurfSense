"""Regression: ``request_approval`` must emit the unified LC HITL wire shape.

Before this fix, self-gated approvals fired the SurfSense-specific
``{type, action, context}`` shape which the parallel-HITL routing layer
(``collect_pending_tool_calls``) does not recognize. In a parallel HITL
scenario where one subagent used self-gated approvals (e.g. Gmail send)
and another used middleware-gated approvals (e.g. Linear via
``HumanInTheLoopMiddleware``), the routing layer would silently skip the
self-gated interrupt and crash on resume with ``Decision count mismatch``.

This test pins the wire contract by running ``request_approval`` inside a
real ``StateGraph`` and asserting the paused parent observes the LC HITL
shape (``action_requests``, ``review_configs``, ``interrupt_type``).
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from typing_extensions import TypedDict

from app.agents.multi_agent_chat.subagents.shared.hitl.approvals.self_gated import (
    request_approval,
)


class _State(TypedDict, total=False):
    messages: list
    final_decision_type: str
    final_params: dict


def _build_graph_calling_request_approval(checkpointer: InMemorySaver):
    """A real graph whose only node delegates to ``request_approval``."""

    def gate_node(_state):
        result = request_approval(
            action_type="gmail_email_send",
            tool_name="send_gmail_email",
            params={"to": "alice@example.com", "subject": "hi"},
            context={"account": "alice@gmail.com"},
        )
        return {
            "final_decision_type": result.decision_type,
            "final_params": result.params,
        }

    g = StateGraph(_State)
    g.add_node("gate", gate_node)
    g.add_edge(START, "gate")
    g.add_edge("gate", END)
    return g.compile(checkpointer=checkpointer)


@pytest.mark.asyncio
async def test_paused_interrupt_uses_lc_hitl_action_requests_shape():
    """The paused interrupt must speak the langchain HITL standard shape."""
    checkpointer = InMemorySaver()
    graph = _build_graph_calling_request_approval(checkpointer)
    config = {"configurable": {"thread_id": "self-gated-wire"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    snap = await graph.aget_state(config)
    assert len(snap.interrupts) == 1, (
        f"expected one paused interrupt, got {len(snap.interrupts)}"
    )
    value = snap.interrupts[0].value
    assert isinstance(value, dict)

    # Standard LC HITL fields the routing layer reads.
    assert value.get("action_requests") == [
        {
            "name": "send_gmail_email",
            "args": {"to": "alice@example.com", "subject": "hi"},
        }
    ], (
        "REGRESSION: self-gated approval reverted to legacy SurfSense shape; "
        f"got {value!r}"
    )
    assert value.get("review_configs") == [
        {
            "action_name": "send_gmail_email",
            "allowed_decisions": ["approve", "reject", "edit"],
        }
    ]
    assert value.get("interrupt_type") == "gmail_email_send", (
        "FE card discriminator must travel as ``interrupt_type``."
    )
    assert value.get("context") == {"account": "alice@gmail.com"}


@pytest.mark.asyncio
async def test_resume_with_lc_envelope_returns_hitl_result_with_edited_args():
    """Edit reply via the LC envelope must round-trip into ``HITLResult.params``."""
    checkpointer = InMemorySaver()
    graph = _build_graph_calling_request_approval(checkpointer)
    config = {"configurable": {"thread_id": "self-gated-resume"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    edited = {"to": "alice@example.com", "subject": "EDITED"}
    await graph.ainvoke(
        Command(
            resume={
                "decisions": [
                    {"type": "edit", "edited_action": {"args": {"subject": "EDITED"}}}
                ]
            }
        ),
        config,
    )
    final = await graph.aget_state(config)
    assert final.values.get("final_decision_type") == "edit"
    assert final.values.get("final_params") == edited


@pytest.mark.asyncio
async def test_reject_envelope_returns_rejected_hitl_result():
    """Reject reply must surface as ``HITLResult.rejected=True`` without invoking the tool."""
    checkpointer = InMemorySaver()
    graph = _build_graph_calling_request_approval(checkpointer)
    config = {"configurable": {"thread_id": "self-gated-reject"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    await graph.ainvoke(
        Command(resume={"decisions": [{"type": "reject", "feedback": "no"}]}),
        config,
    )
    final = await graph.aget_state(config)
    assert final.values.get("final_decision_type") == "reject"
