"""Real-graph contract: heterogeneous decisions route correctly across parallel subagents.

The simple "approve everything" parallel test (see
``test_parallel_resume_command_keying``) proves the routing wires up at all,
but it doesn't exercise the actual production user flow: rejecting one card
while approving another, or editing one action's args before approving the
rest. Those are the decisions ``HumanInTheLoopMiddleware`` differentiates on,
and they're exactly where a slicer/router bug silently mis-applies a reject
to the wrong subagent.

This module pins:

1. **Order preservation** across the slice boundary — flat decisions enter
   in the order the SSE stream rendered cards; each subagent must receive
   only its slice in the original order.
2. **Per-decision metadata pass-through** — ``message`` and ``edited_action``
   payloads must reach the subagent intact (not just the ``type`` discriminator).
3. **Off-by-one-sensitive bundle sizes** — both paused subagents have action
   counts ``> 1`` (``2`` and ``3``). With those sizes a buggy
   ``cursor += 1`` slicer (instead of ``cursor += action_count``) produces a
   different B-slice from the correct one, so this test catches the most
   common refactor mistake. A ``(1, 2)`` configuration would silently pass
   such a bug because ``+= 1`` and ``+= count`` are arithmetically identical
   when ``count == 1``.
"""

from __future__ import annotations

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
    messages: list


class _DispatchState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    tcid: str
    desc: str
    subtype: str


def _build_capturing_subagent(checkpointer: InMemorySaver, *, action_count: int):
    """Subagent that pauses with an N-action bundle and on resume records what it received.

    The recorded ``AIMessage`` content is the JSON-serialized resume payload, so
    the assertions can inspect exactly which decisions reached this subagent
    (vs. its sibling) — including the ``message`` and ``edited_action``
    metadata, not just the ``type``.
    """

    def hitl_node(_state):
        decision_payload = interrupt(
            {
                "action_requests": [
                    {
                        "name": f"act_{i}",
                        "args": {"i": i},
                        "description": f"action {i}",
                    }
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


def _parent_dispatching_two_subagents(
    task_tool, *, dispatches: list[dict[str, str]], checkpointer
):
    """Parent that fans out to ``len(dispatches)`` parallel ``task`` tool calls.

    Each entry in ``dispatches`` is ``{"tcid": ..., "subtype": ..., "desc": ...}``
    so different parallel branches can target different subagent types — the
    actual production scenario (Linear + Jira, etc.).
    """

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
async def test_heterogeneous_decisions_route_to_correct_subagents_with_metadata_intact():
    """Mixed approve/reject/edit decisions across two parallel subagents.

    Setup chosen so the slicer's cursor arithmetic is sensitive to off-by-one
    refactors:
    - Sub-A pauses with a 2-action bundle (``act_0``, ``act_1``).
    - Sub-B pauses with a 3-action bundle (``act_0``, ``act_1``, ``act_2``).
    - Parent ends up with 2 pending interrupts (one per subagent).

    With both counts ``> 1``, a buggy ``cursor += 1`` (instead of
    ``cursor += action_count``) produces a different B-slice from the correct
    one, so the assertions catch it. A ``(1, 2)`` configuration would not
    because ``+= 1`` and ``+= count`` are arithmetically identical when
    ``count == 1``.

    The frontend submits a flat
    ``[A_approve, A_reject, B_edit, B_approve, B_reject]`` list with distinct
    ``message`` and ``edited_action`` payloads; our slicer must split into
    ``{tcid_A: [A_approve, A_reject], tcid_B: [B_edit, B_approve, B_reject]}``
    and the bridge must forward each subagent's slice intact — including all
    metadata, in original order.
    """
    checkpointer = InMemorySaver()

    sub_a = _build_capturing_subagent(checkpointer, action_count=2)
    sub_b = _build_capturing_subagent(checkpointer, action_count=3)

    task_tool = build_task_tool_with_parent_config(
        [
            {"name": "agent-a", "description": "first", "runnable": sub_a},
            {"name": "agent-b", "description": "second", "runnable": sub_b},
        ]
    )

    parent = _parent_dispatching_two_subagents(
        task_tool,
        dispatches=[
            {"tcid": "tcid-A", "subtype": "agent-a", "desc": "do A"},
            {"tcid": "tcid-B", "subtype": "agent-b", "desc": "do B"},
        ],
        checkpointer=checkpointer,
    )

    config: dict = {
        "configurable": {"thread_id": "het-decisions-thread"},
        "recursion_limit": 100,
    }
    await parent.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    paused_state = await parent.aget_state(config)
    assert len(paused_state.interrupts) == 2, (
        f"fixture broken: expected 2 paused subagents, got {len(paused_state.interrupts)}"
    )

    pending = collect_pending_tool_calls(paused_state)
    pending_by_tcid = dict(pending)
    assert pending_by_tcid == {"tcid-A": 2, "tcid-B": 3}, (
        f"REGRESSION: action-count accounting wrong; got {pending_by_tcid!r}"
    )

    a_approve = {"type": "approve"}
    a_reject = {"type": "reject", "message": "A[1] looks redundant"}
    b_edit = {
        "type": "edit",
        "edited_action": {"name": "act_0", "args": {"i": 0, "edited": True}},
    }
    b_approve = {"type": "approve"}
    b_reject = {"type": "reject", "message": "B[2] needs more context"}
    flat_decisions = [a_approve, a_reject, b_edit, b_approve, b_reject]

    by_tool_call_id = slice_decisions_by_tool_call(flat_decisions, pending)

    assert by_tool_call_id == {
        "tcid-A": {"decisions": [a_approve, a_reject]},
        "tcid-B": {"decisions": [b_edit, b_approve, b_reject]},
    }, f"REGRESSION: slicer mis-routed decisions: {by_tool_call_id!r}"

    config["configurable"]["surfsense_resume_value"] = by_tool_call_id
    lg_resume_map = build_lg_resume_map(paused_state, by_tool_call_id)

    await parent.ainvoke(Command(resume=lg_resume_map), config)

    final_state = await parent.aget_state(config)
    assert not final_state.interrupts, (
        f"REGRESSION: leftover pending interrupts after resume: {final_state.interrupts!r}"
    )

    payloads: list[dict] = []
    for msg in final_state.values.get("messages", []) or []:
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            try:
                payloads.append(json.loads(content))
            except json.JSONDecodeError:
                pass

    expected_a = {"decisions": [a_approve, a_reject]}
    expected_b = {"decisions": [b_edit, b_approve, b_reject]}

    assert expected_a in payloads, (
        f"REGRESSION: sub-A did not receive its 2-decision slice in original order; "
        f"payloads seen: {payloads!r}"
    )
    assert expected_b in payloads, (
        f"REGRESSION: sub-B did not receive its 3-decision slice in original order; "
        f"payloads seen: {payloads!r}"
    )


@pytest.mark.asyncio
async def test_decision_count_mismatch_fails_loud_before_dispatch():
    """The slicer must refuse a flat list whose total != sum(action_counts).

    Otherwise a frontend/backend contract drift would silently send a
    truncated/padded slice to one of the subagents — the worst possible
    failure mode (mis-applied reject on a long-lived ticket).
    """
    pending = [("tcid-A", 1), ("tcid-B", 2)]
    decisions = [{"type": "approve"}, {"type": "approve"}]

    with pytest.raises(ValueError, match="Decision count mismatch"):
        slice_decisions_by_tool_call(decisions, pending)
