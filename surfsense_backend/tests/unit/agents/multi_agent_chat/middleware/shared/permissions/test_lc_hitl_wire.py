"""Regression: ``request_permission_decision`` must emit the unified LC HITL wire shape.

Same bug class as :mod:`test_lc_hitl_wire` for self-gated approvals: the
permission middleware previously fired the SurfSense-specific
``{type, action, context}`` shape, which the parallel-HITL routing layer
does not recognize. Standardizing on LC HITL keeps every approval kind on
one routing path.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from typing_extensions import TypedDict

from app.agents.multi_agent_chat.middleware.shared.permissions.ask.request import (
    request_permission_decision,
)
from app.agents.new_chat.permissions import Rule


class _State(TypedDict, total=False):
    messages: list
    final_decision: dict


def _build_graph_calling_request_permission_decision(checkpointer: InMemorySaver):
    """Real graph whose only node delegates to the permission ask primitive."""

    def perm_node(_state):
        decision = request_permission_decision(
            tool_name="rm",
            args={"path": "/tmp/file"},
            patterns=["rm/*"],
            rules=[Rule(permission="rm", pattern="*", action="ask")],
            emit_interrupt=True,
        )
        return {"final_decision": decision}

    g = StateGraph(_State)
    g.add_node("perm", perm_node)
    g.add_edge(START, "perm")
    g.add_edge("perm", END)
    return g.compile(checkpointer=checkpointer)


@pytest.mark.asyncio
async def test_permission_ask_payload_uses_lc_hitl_shape():
    """The permission middleware now speaks the langchain HITL standard shape."""
    checkpointer = InMemorySaver()
    graph = _build_graph_calling_request_permission_decision(checkpointer)
    config = {"configurable": {"thread_id": "perm-wire"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    snap = await graph.aget_state(config)
    assert len(snap.interrupts) == 1
    value = snap.interrupts[0].value

    assert value.get("action_requests") == [
        {"name": "rm", "args": {"path": "/tmp/file"}}
    ], f"REGRESSION: permission ask reverted to legacy shape; got {value!r}"
    review = value.get("review_configs")
    assert isinstance(review, list) and len(review) == 1
    # ``approve_always`` must be in the palette so the FE can render the promote button.
    assert "approve_always" in review[0]["allowed_decisions"]
    assert value.get("interrupt_type") == "permission_ask"
    # SurfSense context rides through verbatim for FE explainability.
    assert value["context"]["patterns"] == ["rm/*"]
    assert value["context"]["always"] == ["rm/*"]


@pytest.mark.asyncio
async def test_resume_with_approve_envelope_returns_once_decision():
    """``approve`` from the LC envelope projects to permission-domain ``once``."""
    checkpointer = InMemorySaver()
    graph = _build_graph_calling_request_permission_decision(checkpointer)
    config = {"configurable": {"thread_id": "perm-once"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    await graph.ainvoke(
        Command(resume={"decisions": [{"type": "approve"}]}), config
    )
    final = await graph.aget_state(config)
    assert final.values.get("final_decision") == {"decision_type": "once"}


@pytest.mark.asyncio
async def test_resume_with_approve_always_envelope_projects_unchanged():
    """``approve_always`` reply must project unchanged so the middleware can promote the rule."""
    checkpointer = InMemorySaver()
    graph = _build_graph_calling_request_permission_decision(checkpointer)
    config = {"configurable": {"thread_id": "perm-approve-always"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    await graph.ainvoke(
        Command(resume={"decisions": [{"type": "approve_always"}]}), config
    )
    final = await graph.aget_state(config)
    assert final.values.get("final_decision") == {"decision_type": "approve_always"}


@pytest.mark.asyncio
async def test_resume_with_reject_and_feedback_carries_feedback_through():
    """Reject feedback must survive normalization for ``CorrectedError`` to fire downstream."""
    checkpointer = InMemorySaver()
    graph = _build_graph_calling_request_permission_decision(checkpointer)
    config = {"configurable": {"thread_id": "perm-reject"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    await graph.ainvoke(
        Command(
            resume={
                "decisions": [{"type": "reject", "feedback": "use the trash bin"}]
            }
        ),
        config,
    )
    final = await graph.aget_state(config)
    assert final.values.get("final_decision") == {
        "decision_type": "reject",
        "feedback": "use the trash bin",
    }
