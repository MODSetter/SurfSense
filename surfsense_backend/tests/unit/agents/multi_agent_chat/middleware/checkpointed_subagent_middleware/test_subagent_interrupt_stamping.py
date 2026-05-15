"""Production-shape regression tests for ``tool_call_id`` stamping on subagent interrupts.

The production bug we're pinning here: when the orchestrator dispatches one or
more ``task`` tool calls and the targeted subagents hit a HITL ``interrupt(...)``,
the parent's persisted ``state.interrupts`` must carry the parent's
``tool_call_id`` on each interrupt value. Without that stamp,
``stream_resume_chat`` cannot route a flat ``decisions`` list back to the right
paused subagent and resume fails with ``Decision count mismatch``.

The tests in this module:

- Build a **real** ``StateGraph`` subagent that calls real ``interrupt(...)``
  (no MagicMock, no patch of langgraph internals — those are exactly the kind
  of fakes that hid this bug).
- Invoke the ``task`` tool from **inside a parent pregel** (via a tiny parent
  ``StateGraph`` node) so the subagent invocation happens in the
  production-shape "subgraph called from a parent tool node" context.
- Assert on ``parent.state.interrupts[*].value["tool_call_id"]`` — the
  observable that ``stream_resume_chat`` reads.
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


class _S(TypedDict, total=False):
    messages: list


def _build_single_interrupt_subagent(checkpointer: InMemorySaver):
    """Subagent that fires one HITL-bundle-shaped interrupt and waits for a decision."""

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

    g = StateGraph(_S)
    g.add_node("approve", approve_node)
    g.add_edge(START, "approve")
    g.add_edge("approve", END)
    return g.compile(checkpointer=checkpointer)


def _build_bundle_subagent(checkpointer: InMemorySaver):
    """Subagent that fires one interrupt carrying a 3-action bundle."""

    def bundle_node(_state):
        decision = interrupt(
            {
                "action_requests": [
                    {"name": "a", "args": {}, "description": ""},
                    {"name": "b", "args": {}, "description": ""},
                    {"name": "c", "args": {}, "description": ""},
                ],
                "review_configs": [{}, {}, {}],
            }
        )
        return {"messages": [AIMessage(content=f"bundle:{decision}")]}

    g = StateGraph(_S)
    g.add_node("bundle", bundle_node)
    g.add_edge(START, "bundle")
    g.add_edge("bundle", END)
    return g.compile(checkpointer=checkpointer)


def _parent_graph_calling_task(task_tool, *, tool_call_id: str, checkpointer):
    """A tiny parent graph whose only node invokes ``task_tool`` from inside the pregel runtime.

    This is the minimal reproduction of production's "subagent invoked from
    inside a parent tool node" context — the *only* context where langgraph
    treats the subagent as a subgraph and routes its interrupts back to the
    parent's checkpoint.
    """

    async def call_task(state, config: RunnableConfig):
        rt = ToolRuntime(
            state=state,
            config=config,
            context=None,
            stream_writer=None,
            tool_call_id=tool_call_id,
            store=None,
        )
        return await task_tool.coroutine(
            description="please approve",
            subagent_type="approver",
            runtime=rt,
        )

    g = StateGraph(_S)
    g.add_node("call_task", call_task)
    g.add_edge(START, "call_task")
    g.add_edge("call_task", END)
    return g.compile(checkpointer=checkpointer)


class _DispatchState(TypedDict, total=False):
    messages: list
    tcid: str
    desc: str


def _parent_graph_dispatching_two_tasks_via_send(
    task_tool, *, tool_call_id_a: str, tool_call_id_b: str, checkpointer
):
    """A parent graph that dispatches two ``task`` calls as parallel pregel
    tasks via :class:`~langgraph.types.Send`.

    This mirrors the production dispatch mechanism: when the orchestrator's
    LLM emits two ``task`` tool calls in one turn, langchain's tool node
    fans them out as parallel pregel tasks (the same primitive as ``Send``)
    so each tool call gets its own pregel task that can raise
    ``GraphInterrupt`` independently — and pregel collects *all* of them
    into the parent's snapshot at the end of the superstep.
    """

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


def _parent_interrupt_values(snapshot) -> list[dict]:
    """Extract ``state.interrupts[*].value`` for assertions."""
    return [i.value for i in (snapshot.interrupts or ())]


@pytest.mark.asyncio
async def test_single_subagent_interrupt_stamps_parent_tool_call_id():
    """A single paused subagent must surface to the parent with ``tool_call_id`` stamped.

    Production bug regression: was producing
    ``value={"action_requests": [...], "review_configs": [...]}`` (no
    ``tool_call_id``), causing ``stream_resume_chat`` to skip the interrupt
    and raise ``Decision count mismatch``.
    """
    checkpointer = InMemorySaver()
    subagent = _build_single_interrupt_subagent(checkpointer)
    task_tool = build_task_tool_with_parent_config(
        [{"name": "approver", "description": "approves", "runnable": subagent}]
    )
    parent = _parent_graph_calling_task(
        task_tool, tool_call_id="parent-tcid-A", checkpointer=checkpointer
    )

    parent_config = {
        "configurable": {"thread_id": "parent-thread"},
        "recursion_limit": 100,
    }
    await parent.ainvoke({"messages": [HumanMessage(content="seed")]}, parent_config)

    snap = await parent.aget_state(parent_config)
    values = _parent_interrupt_values(snap)
    assert len(values) == 1, (
        f"expected exactly 1 parent interrupt, got {len(values)}: {values!r}"
    )
    value = values[0]
    assert isinstance(value, dict)
    assert value.get("tool_call_id") == "parent-tcid-A", (
        f"REGRESSION: parent interrupt missing/wrong tool_call_id stamp. "
        f"Expected 'parent-tcid-A', got {value.get('tool_call_id')!r}. "
        f"Keys present: {sorted(value.keys())}"
    )
    # The original HITL payload must still be intact alongside the stamp.
    assert value.get("action_requests") == [
        {"name": "do_thing", "args": {"x": 1}, "description": ""}
    ]


@pytest.mark.asyncio
async def test_two_parallel_subagents_each_stamp_their_own_tool_call_id():
    """Two ``task`` calls dispatched in parallel must each carry their own ``tool_call_id``.

    This is the actual production scenario (Linear + Jira ticket creation):
    two parallel ``task`` tool calls, both subagents hit HITL, parent must
    end up with two interrupts whose ``tool_call_id``s match the two
    distinct parent-level ``tool_call_id``s the LLM emitted.
    """
    checkpointer = InMemorySaver()
    subagent = _build_single_interrupt_subagent(checkpointer)
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
        "configurable": {"thread_id": "parent-thread-parallel"},
        "recursion_limit": 100,
    }
    await parent.ainvoke({"messages": [HumanMessage(content="seed")]}, parent_config)

    snap = await parent.aget_state(parent_config)
    values = _parent_interrupt_values(snap)
    assert len(values) == 2, (
        f"expected 2 parent interrupts (one per parallel task call), "
        f"got {len(values)}: {values!r}"
    )
    stamps = {v.get("tool_call_id") for v in values}
    assert stamps == {"parent-tcid-A", "parent-tcid-B"}, (
        f"REGRESSION: parallel parent interrupts missing/wrong tool_call_id stamps. "
        f"Expected {{'parent-tcid-A', 'parent-tcid-B'}}, got {stamps!r}. "
        f"Values: {values!r}"
    )


@pytest.mark.asyncio
async def test_bundle_subagent_interrupt_stamps_tool_call_id_preserving_actions():
    """A subagent emitting a multi-action bundle must surface stamped, with all actions intact.

    The bundle shape (``action_requests=[3 items]``) drives the
    ``slice_decisions_by_tool_call`` accounting in ``stream_resume_chat`` —
    if either the stamp or the action count is lost, resume routing
    miscounts and crashes.
    """
    checkpointer = InMemorySaver()
    subagent = _build_bundle_subagent(checkpointer)
    task_tool = build_task_tool_with_parent_config(
        [{"name": "approver", "description": "approves", "runnable": subagent}]
    )
    parent = _parent_graph_calling_task(
        task_tool, tool_call_id="parent-tcid-bundle", checkpointer=checkpointer
    )

    parent_config = {
        "configurable": {"thread_id": "parent-thread-bundle"},
        "recursion_limit": 100,
    }
    await parent.ainvoke({"messages": [HumanMessage(content="seed")]}, parent_config)

    snap = await parent.aget_state(parent_config)
    values = _parent_interrupt_values(snap)
    assert len(values) == 1
    value = values[0]
    assert value.get("tool_call_id") == "parent-tcid-bundle"
    assert isinstance(value.get("action_requests"), list)
    assert len(value["action_requests"]) == 3, (
        f"REGRESSION: bundle action_requests count changed during stamping; "
        f"got {len(value['action_requests'])} actions: {value['action_requests']!r}"
    )
