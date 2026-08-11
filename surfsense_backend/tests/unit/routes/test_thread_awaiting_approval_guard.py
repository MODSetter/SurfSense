"""A thread paused for HITL must refuse a fresh turn.

The busy mutex releases on an ``interrupt()`` pause, so a paused thread reads
as idle and ``new_chat`` / ``regenerate`` would run over the paused checkpoint,
orphaning the pending approval. ``_raise_if_thread_awaiting_approval`` closes
that gap by reading the checkpoint and refusing with 409.
"""

import pytest
from fastapi import HTTPException
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

from app.routes.new_chat_routes import _raise_if_thread_awaiting_approval


class _S(TypedDict, total=False):
    messages: list


async def _paused_checkpointer(thread_id: int) -> InMemorySaver:
    """Run a graph that interrupts, leaving a pending interrupt in the checkpoint."""

    def node(_s):
        decision = interrupt({"action_requests": [{"name": "x", "args": {}}]})
        return {"messages": [decision]}

    g = StateGraph(_S)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)
    cp = InMemorySaver()
    graph = g.compile(checkpointer=cp)
    await graph.ainvoke(
        {"messages": []}, {"configurable": {"thread_id": str(thread_id)}}
    )
    return cp


@pytest.mark.asyncio
async def test_paused_thread_is_refused_with_409():
    cp = await _paused_checkpointer(1)

    with pytest.raises(HTTPException) as exc:
        await _raise_if_thread_awaiting_approval(1, cp)

    assert exc.value.status_code == 409
    assert exc.value.detail["errorCode"] == "THREAD_AWAITING_APPROVAL"


@pytest.mark.asyncio
async def test_clean_thread_is_allowed():
    def node(_s):
        return {"messages": ["done"]}

    g = StateGraph(_S)
    g.add_node("n", node)
    g.add_edge(START, "n")
    g.add_edge("n", END)
    cp = InMemorySaver()
    graph = g.compile(checkpointer=cp)
    await graph.ainvoke({"messages": []}, {"configurable": {"thread_id": "2"}})

    await _raise_if_thread_awaiting_approval(2, cp)  # no raise


@pytest.mark.asyncio
async def test_thread_without_checkpoint_is_allowed():
    await _raise_if_thread_awaiting_approval(999, InMemorySaver())  # no raise
