"""Real-graph contract: all-reject decisions route correctly across parallel subagents.

Heterogeneous routing is covered by ``test_parallel_heterogeneous_decisions``.
This module pins the narrower edge case where **every** card on **every**
paused subagent is rejected.

Why a separate pin:

1. **No approval-bias in the slicer.** A future "if no approvals, short-circuit
   resume" optimization would be tempting (skips a langgraph round-trip) and
   would also silently break this scenario. Pin it.
2. **``message`` metadata pass-through across a run of rejects.** The reject
   ``message`` is the user-visible reason ("looks suspicious", "duplicate",
   etc.). Losing it would silently swallow user intent — the worst UX
   failure mode for HITL. Heterogeneous covers one reject; here we verify a
   sequence of rejects survives the slicer + bridge with distinct messages
   intact and in order.
3. **All branches complete with no leftover pending.** Even when nothing was
   approved, the parent must drain every paused subagent so the SSE stream
   can close cleanly. A bug that left one ``Interrupt.id`` un-keyed would
   strand the conversation in "pending" forever.
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

from app.agents.chat.multi_agent_chat.main_agent.middleware.checkpointed_subagent_middleware.resume_routing import (
    build_lg_resume_map,
    collect_pending_tool_calls,
    slice_decisions_by_tool_call,
)
from app.agents.chat.multi_agent_chat.main_agent.middleware.checkpointed_subagent_middleware.task_tool import (
    build_task_tool_with_parent_config,
)


class _SubState(TypedDict, total=False):
    messages: list


class _DispatchState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    tcid: str
    desc: str
    subtype: str


def _build_recording_subagent(checkpointer: InMemorySaver, *, action_count: int):
    """Subagent that pauses with ``action_count`` actions and records its resume payload.

    The recorded ``AIMessage`` content is the JSON-serialized payload, so the
    test can match each subagent's slice by content.
    """

    def hitl_node(_state):
        decision_payload = interrupt(
            {
                "action_requests": [
                    {"name": f"act_{i}", "args": {"i": i}, "description": ""}
                    for i in range(action_count)
                ],
                "review_configs": [
                    {
                        "action_name": f"act_{i}",
                        "allowed_decisions": ["approve", "reject", "edit"],
                    }
                    for i in range(action_count)
                ],
            }
        )
        return {
            "messages": [
                AIMessage(content=json.dumps(decision_payload, sort_keys=True))
            ]
        }

    g = StateGraph(_SubState)
    g.add_node("hitl", hitl_node)
    g.add_edge(START, "hitl")
    g.add_edge("hitl", END)
    return g.compile(checkpointer=checkpointer)


def _parent_two_branches(task_tool, *, dispatches, checkpointer):
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


@pytest.mark.asyncio
async def test_all_reject_decisions_route_to_each_subagent_with_messages_intact():
    """All cards rejected across two parallel subagents — order and messages preserved.

    Setup mirrors a real "user reviews two parallel ticket creations and
    rejects everything with distinct reasons":

    - Sub-A pauses with 2 actions.
    - Sub-B pauses with 1 action.
    - Flat decisions: 3 rejects, each with a unique ``message``.

    Asserts each subagent receives only its slice, in original order,
    with every ``message`` intact and no ``edited_action`` fields fabricated.
    """
    checkpointer = InMemorySaver()

    sub_a = _build_recording_subagent(checkpointer, action_count=2)
    sub_b = _build_recording_subagent(checkpointer, action_count=1)

    task_tool = build_task_tool_with_parent_config(
        [
            {"name": "agent-a", "description": "first", "runnable": sub_a},
            {"name": "agent-b", "description": "second", "runnable": sub_b},
        ]
    )

    parent = _parent_two_branches(
        task_tool,
        dispatches=[
            {"tcid": "tcid-A", "subtype": "agent-a", "desc": "do A"},
            {"tcid": "tcid-B", "subtype": "agent-b", "desc": "do B"},
        ],
        checkpointer=checkpointer,
    )

    config: dict = {
        "configurable": {"thread_id": "all-reject-thread"},
        "recursion_limit": 100,
    }
    await parent.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    paused_state = await parent.aget_state(config)
    assert len(paused_state.interrupts) == 2, (
        f"fixture broken: expected 2 paused subagents, got {len(paused_state.interrupts)}"
    )

    a_reject_0 = {"type": "reject", "message": "A[0] looks suspicious"}
    a_reject_1 = {"type": "reject", "message": "A[1] duplicates A[0]"}
    b_reject_0 = {"type": "reject", "message": "B[0] needs more context"}
    flat_decisions = [a_reject_0, a_reject_1, b_reject_0]

    pending = collect_pending_tool_calls(paused_state)
    by_tool_call_id = slice_decisions_by_tool_call(flat_decisions, pending)

    assert by_tool_call_id == {
        "tcid-A": {"decisions": [a_reject_0, a_reject_1]},
        "tcid-B": {"decisions": [b_reject_0]},
    }, f"REGRESSION: slicer mis-routed all-reject decisions: {by_tool_call_id!r}"

    config["configurable"]["surfsense_resume_value"] = by_tool_call_id
    lg_resume_map = build_lg_resume_map(paused_state, by_tool_call_id)

    await parent.ainvoke(Command(resume=lg_resume_map), config)

    final_state = await parent.aget_state(config)
    assert not final_state.interrupts, (
        f"REGRESSION: leftover pending interrupts after all-reject resume: "
        f"{final_state.interrupts!r}"
    )

    payloads: list[dict] = []
    for msg in final_state.values.get("messages", []) or []:
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            with contextlib.suppress(json.JSONDecodeError):
                payloads.append(json.loads(content))

    expected_a = {"decisions": [a_reject_0, a_reject_1]}
    expected_b = {"decisions": [b_reject_0]}

    assert expected_a in payloads, (
        f"REGRESSION: sub-A did not receive its 2-reject slice in order; "
        f"payloads seen: {payloads!r}"
    )
    assert expected_b in payloads, (
        f"REGRESSION: sub-B did not receive its single reject; "
        f"payloads seen: {payloads!r}"
    )

    for p in payloads:
        for d in p.get("decisions", []):
            assert "edited_action" not in d, (
                f"REGRESSION: spurious ``edited_action`` on a reject — "
                f"slicer/bridge mutated payload: {d!r}"
            )
