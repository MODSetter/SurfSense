"""Real-graph contract: ``all_interrupt_values`` surfaces every pending interrupt.

The chat-stream emit loop must yield one ``data-interrupt-request`` SSE frame
per paused subagent, in the same order ``state.interrupts`` reports them —
that's also the order the resume slicer consumes decisions. These tests pin
that contract against a **real** paused parent graph built via
:class:`~langgraph.types.Send` fan-out (no synthetic state mocks).
"""

from __future__ import annotations

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt
from typing_extensions import TypedDict

from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.task_tool import (
    build_task_tool_with_parent_config,
)
from app.tasks.chat.streaming.helpers.interrupt_inspector import (
    all_interrupt_values,
)


class _SubState(TypedDict, total=False):
    messages: list


class _DispatchState(TypedDict, total=False):
    messages: list
    tcid: str
    desc: str


def _build_pausing_subagent(checkpointer: InMemorySaver):
    def approve_node(_state):
        decision = interrupt(
            {
                "action_requests": [
                    {"name": "do_thing", "args": {"x": 1}, "description": ""}
                ],
                "review_configs": [{}],
            }
        )
        return {"messages": [AIMessage(content=f"got:{decision}")]}

    g = StateGraph(_SubState)
    g.add_node("approve", approve_node)
    g.add_edge(START, "approve")
    g.add_edge("approve", END)
    return g.compile(checkpointer=checkpointer)


def _parent_graph_dispatching_two_tasks_via_send(
    task_tool, *, tool_call_id_a: str, tool_call_id_b: str, checkpointer
):
    def fanout_edge(_state) -> list[Send]:
        return [
            Send("call_task", {"tcid": tool_call_id_a, "desc": "approve A"}),
            Send("call_task", {"tcid": tool_call_id_b, "desc": "approve B"}),
        ]

    async def call_task(state: _DispatchState, config: RunnableConfig):
        rt = ToolRuntime(
            state=state,
            config=config,
            context=None,
            stream_writer=None,
            tool_call_id=state["tcid"],
            store=None,
        )
        return await task_tool.coroutine(
            description=state["desc"], subagent_type="approver", runtime=rt
        )

    g = StateGraph(_DispatchState)
    g.add_node("call_task", call_task)
    g.add_conditional_edges(START, fanout_edge, ["call_task"])
    g.add_edge("call_task", END)
    return g.compile(checkpointer=checkpointer)


@pytest.mark.asyncio
async def test_returns_every_pending_interrupt_for_two_paused_subagents():
    """Two parallel subagents -> ``all_interrupt_values`` returns 2 dicts."""
    checkpointer = InMemorySaver()
    subagent = _build_pausing_subagent(checkpointer)
    task_tool = build_task_tool_with_parent_config(
        [{"name": "approver", "description": "approves", "runnable": subagent}]
    )
    parent = _parent_graph_dispatching_two_tasks_via_send(
        task_tool,
        tool_call_id_a="parent-tcid-A",
        tool_call_id_b="parent-tcid-B",
        checkpointer=checkpointer,
    )

    parent_config = {
        "configurable": {"thread_id": "all-iv-thread"},
        "recursion_limit": 100,
    }
    await parent.ainvoke({"messages": [HumanMessage(content="seed")]}, parent_config)
    state = await parent.aget_state(parent_config)

    values = all_interrupt_values(state)

    assert isinstance(values, list)
    assert len(values) == 2, (
        f"REGRESSION: expected one value per pending subagent, got "
        f"{len(values)}: {values!r}"
    )
    stamps = [v.get("tool_call_id") for v in values]
    assert sorted(stamps) == ["parent-tcid-A", "parent-tcid-B"]
    for v in values:
        assert isinstance(v.get("action_requests"), list)
        assert len(v["action_requests"]) == 1


@pytest.mark.asyncio
async def test_preserves_state_interrupts_traversal_order():
    """Order returned by inspector must match ``state.interrupts`` order.

    The resume slicer consumes decisions left-to-right against
    ``collect_pending_tool_calls(state)`` which walks ``state.interrupts``
    in iteration order — so the inspector (which drives the *emit* order)
    must agree with that traversal or the slice and the wire fall out of sync.
    """
    checkpointer = InMemorySaver()
    subagent = _build_pausing_subagent(checkpointer)
    task_tool = build_task_tool_with_parent_config(
        [{"name": "approver", "description": "approves", "runnable": subagent}]
    )
    parent = _parent_graph_dispatching_two_tasks_via_send(
        task_tool,
        tool_call_id_a="parent-tcid-A",
        tool_call_id_b="parent-tcid-B",
        checkpointer=checkpointer,
    )
    parent_config = {
        "configurable": {"thread_id": "order-thread"},
        "recursion_limit": 100,
    }
    await parent.ainvoke({"messages": [HumanMessage(content="seed")]}, parent_config)
    state = await parent.aget_state(parent_config)

    inspector_order = [v["tool_call_id"] for v in all_interrupt_values(state)]
    state_order = [
        i.value["tool_call_id"]
        for i in state.interrupts
        if isinstance(getattr(i, "value", None), dict) and "tool_call_id" in i.value
    ]

    assert inspector_order == state_order, (
        f"inspector order {inspector_order!r} diverged from state.interrupts "
        f"order {state_order!r}; the resume slicer would mis-route decisions."
    )


@pytest.mark.asyncio
async def test_returns_empty_list_when_nothing_paused():
    """A graph that completes normally produces no interrupts to surface."""

    def done_node(_state):
        return {"messages": [AIMessage(content="done")]}

    g = StateGraph(_SubState)
    g.add_node("done", done_node)
    g.add_edge(START, "done")
    g.add_edge("done", END)
    graph = g.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "no-pause-thread"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)
    state = await graph.aget_state(config)

    assert all_interrupt_values(state) == []


@pytest.mark.asyncio
async def test_single_paused_subagent_returns_a_list_of_one():
    """Single-pause case must still return a list (not unwrap to a dict)."""

    def approve_node(_state):
        decision = interrupt(
            {
                "action_requests": [{"name": "x", "args": {}, "description": ""}],
                "review_configs": [{}],
                "tool_call_id": "lonely-tcid",
            }
        )
        return {"messages": [AIMessage(content=f"got:{decision}")]}

    g = StateGraph(_SubState)
    g.add_node("approve", approve_node)
    g.add_edge(START, "approve")
    g.add_edge("approve", END)
    graph = g.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "single-thread"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)
    state = await graph.aget_state(config)

    values = all_interrupt_values(state)

    assert isinstance(values, list)
    assert len(values) == 1
    assert values[0].get("tool_call_id") == "lonely-tcid"
