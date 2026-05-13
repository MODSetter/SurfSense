"""Real-graph contract: parallel resume must key ``Command(resume=...)`` by ``Interrupt.id``.

When the parent state has multiple pending interrupts, langgraph rejects a
scalar ``Command(resume=v)`` with::

    RuntimeError: When there are multiple pending interrupts, you must specify
    the interrupt id when resuming.

The fix is to map each ``Interrupt.id`` from ``state.interrupts`` to the
per-subagent slice — orthogonal to our ``tool_call_id``-keyed
``surfsense_resume_value`` side-channel (different consumer: langgraph's
pregel vs. our subagent bridge).

This test reproduces the production failure with a real two-task parallel
``Send`` parent graph, exercises the full resume cycle, and asserts both
subagents complete cleanly.
"""

from __future__ import annotations

from typing import Annotated

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, Send, interrupt
from typing_extensions import TypedDict

from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.resume_routing import (
    build_lg_resume_map,
    collect_pending_tool_calls,
    slice_decisions_by_tool_call,
)
from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.task_tool import (
    build_task_tool_with_parent_config,
)


class _SubState(TypedDict, total=False):
    messages: list


class _DispatchState(TypedDict, total=False):
    # ``add_messages`` reducer matches production agent state shape and is
    # required when two parallel ``Send`` branches both write to ``messages``
    # in the same superstep (post-resume both subagents return their own
    # ``{"messages": [...]}``). Without a reducer langgraph raises
    # ``InvalidUpdateError: At key 'messages': Can receive only one value``.
    messages: Annotated[list, add_messages]
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
async def test_parallel_resume_with_command_resume_scalar_raises_lg_runtime_error():
    """Confirm the production failure mode: scalar resume on multi-pending state explodes.

    This is a contract pin: if langgraph relaxes the requirement in a future
    release, this test starts passing and we know we can simplify
    ``stream_resume_chat``. Until then, the keyed form is mandatory.
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
    config: dict = {
        "configurable": {"thread_id": "parallel-resume-scalar"},
        "recursion_limit": 100,
    }
    await parent.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    with pytest.raises(RuntimeError, match="multiple pending interrupts"):
        await parent.ainvoke(Command(resume={"decisions": ["A"]}), config)


@pytest.mark.asyncio
async def test_parallel_resume_with_per_interrupt_id_keying_completes_both_subagents():
    """Production-shape resume: builds the langgraph-keyed map and resumes both subagents.

    Mirrors what ``stream_resume_chat`` does: collects pending interrupts,
    slices the flat decisions list by ``tool_call_id``, builds the
    ``Interrupt.id``-keyed map for ``Command(resume=...)``, and resumes.
    The expected post-condition is that both subagents pop their own
    decision (via the ``surfsense_resume_value`` side-channel) and run to
    completion — no RuntimeError, no leaked pending interrupts.
    """
    checkpointer = InMemorySaver()
    subagent = _build_pausing_subagent(checkpointer)
    task_tool = build_task_tool_with_parent_config(
        [{"name": "approver", "description": "approves", "runnable": subagent}]
    )
    tcid_a = "parent-tcid-A"
    tcid_b = "parent-tcid-B"
    parent = _parent_graph_dispatching_two_tasks_via_send(
        task_tool,
        tool_call_id_a=tcid_a,
        tool_call_id_b=tcid_b,
        checkpointer=checkpointer,
    )
    config: dict = {
        "configurable": {"thread_id": "parallel-resume-keyed"},
        "recursion_limit": 100,
    }
    await parent.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    paused_state = await parent.aget_state(config)
    assert len(paused_state.interrupts) == 2, "fixture broken: expected 2 paused subagents"

    pending = collect_pending_tool_calls(paused_state)
    flat_decisions = [{"type": "approve"}, {"type": "approve"}]
    by_tool_call_id = slice_decisions_by_tool_call(flat_decisions, pending)
    lg_resume_map = build_lg_resume_map(paused_state, by_tool_call_id)

    assert len(lg_resume_map) == 2, (
        f"expected one entry per pending interrupt id, got {lg_resume_map!r}"
    )
    assert all(isinstance(k, str) for k in lg_resume_map), (
        f"keys must be Interrupt.id strings, got {[type(k).__name__ for k in lg_resume_map]}"
    )

    # Wire the side-channel exactly like ``stream_resume_chat`` does.
    config["configurable"]["surfsense_resume_value"] = by_tool_call_id

    await parent.ainvoke(Command(resume=lg_resume_map), config)

    final_state = await parent.aget_state(config)
    assert not final_state.interrupts, (
        f"expected no leftover pending interrupts after resume, got "
        f"{final_state.interrupts!r}"
    )


def test_build_lg_resume_map_returns_empty_when_no_interrupts_carry_stamps():
    """Unstamped interrupts can't be routed; we don't fabricate keys for them.

    If a regression lets an unstamped interrupt reach the parent state, the
    empty map propagates to the call site and surfaces as a clear count
    mismatch instead of a silent mis-route.
    """
    from types import SimpleNamespace

    fake_interrupt = SimpleNamespace(id="i-foreign", value={"action_requests": [{}]})
    state = SimpleNamespace(interrupts=(fake_interrupt,))

    assert build_lg_resume_map(state, {"some-tcid": {"decisions": ["x"]}}) == {}


def test_build_lg_resume_map_skips_interrupts_without_corresponding_slice():
    """Skip rather than silently mis-route when the slice and interrupts disagree.

    Only emit a resume entry when both an interrupt id and a tool_call_id
    slice are present; a mismatch indicates upstream contract drift and
    should not be papered over.
    """
    from types import SimpleNamespace

    state = SimpleNamespace(
        interrupts=(
            SimpleNamespace(
                id="i-A",
                value={"action_requests": [{}], "tool_call_id": "tcid-A"},
            ),
            SimpleNamespace(
                id="i-B",
                value={"action_requests": [{}], "tool_call_id": "tcid-B"},
            ),
        )
    )

    out = build_lg_resume_map(state, {"tcid-A": {"decisions": ["only-A"]}})
    assert out == {"i-A": {"decisions": ["only-A"]}}
