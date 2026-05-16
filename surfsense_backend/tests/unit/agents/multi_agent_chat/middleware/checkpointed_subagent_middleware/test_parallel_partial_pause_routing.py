"""Real-graph contract: one parallel branch completes while a sibling pauses with HITL.

The two existing parallel-routing tests
(``test_parallel_resume_command_keying`` and
``test_parallel_heterogeneous_decisions``) both pause **all** branches
simultaneously. That's the easy case — every dispatched ``task`` call has a
matching pending interrupt, and the routing helpers see a uniform shape.

Production rarely matches that uniform shape. The orchestrator typically
delegates "create a Linear ticket and summarize the user's recent activity":
one branch needs HITL, the other returns its result and exits. At the pause
moment::

    state.values["messages"] += [ToolMessage(from-A)]   # A merged in
    state.interrupts          = [Interrupt(value-from-B)]   # B alone is pending

So ``len(state.interrupts) < num_dispatched_tasks``. The slicer and
``build_lg_resume_map`` must:

1. **Key off ``state.interrupts``, never off the originally dispatched tcids.**
   A flat decisions list of length 1 must route only to B; if anything tries
   to look up A in the resume map, langgraph rejects an unknown
   ``Interrupt.id``.
2. **Leave A's contributions intact across resume.** A's ToolMessage was
   committed at the pause; resuming the paused branch must not re-run A nor
   drop its message.
3. **Drain the single pending interrupt.** Final ``state.interrupts`` is
   empty regardless of whether sibling branches were paused.

The langgraph semantics this test relies on were verified empirically in the
exploratory probe before this test was authored.
"""

from __future__ import annotations

import contextlib
import json
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
    messages: Annotated[list, add_messages]


class _DispatchState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    tcid: str
    desc: str
    subtype: str


_QUICK_MARKER = "quick-subagent-finished-without-pausing"


def _build_quick_subagent(checkpointer: InMemorySaver):
    """Subagent that completes synchronously without firing any interrupt."""

    def quick_node(_state):
        return {"messages": [AIMessage(content=_QUICK_MARKER)]}

    g = StateGraph(_SubState)
    g.add_node("quick", quick_node)
    g.add_edge(START, "quick")
    g.add_edge("quick", END)
    return g.compile(checkpointer=checkpointer)


def _build_pausing_subagent(checkpointer: InMemorySaver):
    """Subagent that pauses with a single-action HITL bundle and records its resume payload."""

    def hitl_node(_state):
        decision = interrupt(
            {
                "action_requests": [
                    {"name": "act_0", "args": {"i": 0}, "description": ""}
                ],
                "review_configs": [
                    {
                        "action_name": "act_0",
                        "allowed_decisions": ["approve", "reject", "edit"],
                    }
                ],
            }
        )
        return {"messages": [AIMessage(content=json.dumps(decision, sort_keys=True))]}

    g = StateGraph(_SubState)
    g.add_node("hitl", hitl_node)
    g.add_edge(START, "hitl")
    g.add_edge("hitl", END)
    return g.compile(checkpointer=checkpointer)


def _parent_with_two_branches(task_tool, *, dispatches, checkpointer):
    def fanout(_state) -> list[Send]:
        return [Send("call_task", d) for d in dispatches]

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
            description=state["desc"], subagent_type=state["subtype"], runtime=rt
        )

    g = StateGraph(_DispatchState)
    g.add_node("call_task", call_task)
    g.add_conditional_edges(START, fanout, ["call_task"])
    g.add_edge("call_task", END)
    return g.compile(checkpointer=checkpointer)


def _quick_marker_count(state) -> int:
    """How many messages anywhere in parent state contain the quick subagent's marker."""
    n = 0
    for msg in state.values.get("messages", []) or []:
        content = getattr(msg, "content", "")
        if isinstance(content, str) and _QUICK_MARKER in content:
            n += 1
    return n


@pytest.mark.asyncio
async def test_partial_pause_routes_only_to_paused_branch_without_rerunning_completed_one():
    """One branch completes synchronously; the other pauses with HITL — resume routes only to B.

    Setup:
    - Sub-A (``quick``): no interrupt, finishes immediately, writes a marker
      message to parent state.
    - Sub-B (``pausing``): interrupts with a 1-action HITL bundle.

    At pause, parent state has A's marker already merged in and exactly one
    pending interrupt (B's). Resume sends a 1-element flat decisions list;
    the routing helpers must not look up A in the resume map (would explode
    with an unknown ``Interrupt.id``) and must not re-invoke A on resume
    (would duplicate the marker).
    """
    checkpointer = InMemorySaver()

    quick_sub = _build_quick_subagent(checkpointer)
    pausing_sub = _build_pausing_subagent(checkpointer)

    task_tool = build_task_tool_with_parent_config(
        [
            {"name": "quick-agent", "description": "instant", "runnable": quick_sub},
            {
                "name": "pausing-agent",
                "description": "needs review",
                "runnable": pausing_sub,
            },
        ]
    )

    parent = _parent_with_two_branches(
        task_tool,
        dispatches=[
            {"tcid": "tcid-A", "subtype": "quick-agent", "desc": "do A fast"},
            {
                "tcid": "tcid-B",
                "subtype": "pausing-agent",
                "desc": "needs approval",
            },
        ],
        checkpointer=checkpointer,
    )

    config: dict = {
        "configurable": {"thread_id": "partial-pause-thread"},
        "recursion_limit": 100,
    }
    await parent.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    paused = await parent.aget_state(config)

    assert len(paused.interrupts) == 1, (
        f"REGRESSION: expected exactly 1 pending interrupt (sub-B alone), "
        f"got {len(paused.interrupts)}"
    )

    pending = collect_pending_tool_calls(paused)
    assert pending == [("tcid-B", 1)], (
        f"REGRESSION: pending list contains stale tcids; got {pending!r}"
    )

    pre_resume_marker_count = _quick_marker_count(paused)
    assert pre_resume_marker_count == 1, (
        f"REGRESSION: sub-A's contribution missing or duplicated at pause "
        f"(found {pre_resume_marker_count}, expected 1)"
    )

    flat_decisions = [{"type": "approve"}]
    by_tool_call_id = slice_decisions_by_tool_call(flat_decisions, pending)
    assert by_tool_call_id == {"tcid-B": {"decisions": [{"type": "approve"}]}}, (
        f"REGRESSION: slicer routed to a non-pending tcid: {by_tool_call_id!r}"
    )

    config["configurable"]["surfsense_resume_value"] = by_tool_call_id
    lg_resume_map = build_lg_resume_map(paused, by_tool_call_id)

    assert set(lg_resume_map.keys()) == {paused.interrupts[0].id}, (
        f"REGRESSION: resume map keyed by an unknown Interrupt.id "
        f"(would crash langgraph): {lg_resume_map!r}"
    )

    await parent.ainvoke(Command(resume=lg_resume_map), config)

    final = await parent.aget_state(config)
    assert not final.interrupts, (
        f"REGRESSION: pending interrupts after resume: {final.interrupts!r}"
    )

    post_resume_marker_count = _quick_marker_count(final)
    assert post_resume_marker_count == 1, (
        f"REGRESSION: sub-A re-ran on resume (marker count went "
        f"{pre_resume_marker_count} → {post_resume_marker_count}); "
        f"resume must touch only the paused branch."
    )

    payloads: list[dict] = []
    for msg in final.values.get("messages", []) or []:
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            with contextlib.suppress(json.JSONDecodeError):
                payloads.append(json.loads(content))

    assert {"decisions": [{"type": "approve"}]} in payloads, (
        f"REGRESSION: sub-B did not receive its single approve on resume; "
        f"payloads seen: {payloads!r}"
    )
