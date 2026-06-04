"""Real-graph parallel HITL across both approval kinds — the keystone regression.

Pre-fix bug: the parallel-HITL routing layer (``collect_pending_tool_calls``
+ ``slice_decisions_by_tool_call`` + ``build_lg_resume_map``) only
recognized middleware-gated approvals (LC HITL shape from
``HumanInTheLoopMiddleware``). Self-gated approvals from
``request_approval`` and middleware-gated permission asks from
``PermissionMiddleware`` both used the SurfSense-specific
``{type, action, context}`` shape, so when the orchestrator dispatched
two parallel ``task`` calls — one self-gated, one middleware-gated — only
one interrupt was visible to the routing layer and resume crashed with
``Decision count mismatch``.

This test fans out two real subagents via ``Send``: one calls
``request_approval`` (self-gated), the other calls
``request_permission_decision`` (middleware-gated). Both pause; the routing
layer must see TWO LC HITL interrupts, slice the decisions by
``tool_call_id``, key by ``Interrupt.id``, and resume both branches with
their per-slice payload.
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
from langgraph.types import Command, Send
from typing_extensions import TypedDict

from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.resume_routing import (
    build_lg_resume_map,
    collect_pending_tool_calls,
    slice_decisions_by_tool_call,
)
from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.task_tool import (
    build_task_tool_with_parent_config,
)
from app.agents.multi_agent_chat.middleware.shared.permissions.ask.request import (
    request_permission_decision,
)
from app.agents.multi_agent_chat.subagents.shared.hitl.approvals.self_gated import (
    request_approval,
)
from app.agents.shared.permissions import Rule


class _SubState(TypedDict, total=False):
    messages: list


class _DispatchState(TypedDict, total=False):
    # ``add_messages`` is mandatory: parallel ``Send`` branches both append
    # to ``messages`` in the same superstep; without a reducer langgraph
    # raises ``InvalidUpdateError``.
    messages: Annotated[list, add_messages]
    tcid: str
    desc: str
    subtype: str


def _build_self_gated_subagent(checkpointer: InMemorySaver):
    """Subagent that pauses via ``request_approval`` (self-gated path)."""

    def gate_node(_state):
        result = request_approval(
            action_type="gmail_email_send",
            tool_name="send_gmail_email",
            params={"to": "alice@example.com"},
        )
        return {
            "messages": [
                AIMessage(
                    content=json.dumps(
                        {
                            "kind": "self_gated",
                            "decision_type": result.decision_type,
                            "params": result.params,
                            "rejected": result.rejected,
                        },
                        sort_keys=True,
                    )
                )
            ]
        }

    g = StateGraph(_SubState)
    g.add_node("gate", gate_node)
    g.add_edge(START, "gate")
    g.add_edge("gate", END)
    return g.compile(checkpointer=checkpointer)


def _build_middleware_gated_subagent(checkpointer: InMemorySaver):
    """Subagent that pauses via ``request_permission_decision`` (middleware-gated path)."""

    def perm_node(_state):
        decision = request_permission_decision(
            tool_name="rm",
            args={"path": "/tmp/file"},
            patterns=["rm/*"],
            rules=[Rule(permission="rm", pattern="*", action="ask")],
            emit_interrupt=True,
        )
        return {
            "messages": [
                AIMessage(
                    content=json.dumps(
                        {"kind": "middleware_gated", "decision": decision},
                        sort_keys=True,
                    )
                )
            ]
        }

    g = StateGraph(_SubState)
    g.add_node("perm", perm_node)
    g.add_edge(START, "perm")
    g.add_edge("perm", END)
    return g.compile(checkpointer=checkpointer)


def _build_mixed_task_tool(checkpointer: InMemorySaver):
    """Two subagents, one per approval kind, registered under distinct names."""
    return build_task_tool_with_parent_config(
        [
            {
                "name": "self-gated-agent",
                "description": "uses request_approval",
                "runnable": _build_self_gated_subagent(checkpointer),
            },
            {
                "name": "middleware-gated-agent",
                "description": "uses request_permission_decision",
                "runnable": _build_middleware_gated_subagent(checkpointer),
            },
        ]
    )


def _parent_dispatching_one_of_each(
    task_tool, *, tcid_self: str, tcid_mw: str, checkpointer
):
    def fanout_edge(_state) -> list[Send]:
        return [
            Send(
                "call_task",
                {
                    "tcid": tcid_self,
                    "desc": "approve email",
                    "subtype": "self-gated-agent",
                },
            ),
            Send(
                "call_task",
                {
                    "tcid": tcid_mw,
                    "desc": "approve rm",
                    "subtype": "middleware-gated-agent",
                },
            ),
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
            description=state["desc"], subagent_type=state["subtype"], runtime=rt
        )

    g = StateGraph(_DispatchState)
    g.add_node("call_task", call_task)
    g.add_conditional_edges(START, fanout_edge, ["call_task"])
    g.add_edge("call_task", END)
    return g.compile(checkpointer=checkpointer)


@pytest.mark.asyncio
async def test_parallel_self_gated_and_middleware_gated_route_and_resume_cleanly():
    """Both interrupt kinds must reach the routing layer in LC HITL shape and resume independently."""
    checkpointer = InMemorySaver()
    task_tool = _build_mixed_task_tool(checkpointer)
    tcid_self = "tcid-self-gated"
    tcid_mw = "tcid-middleware-gated"
    parent = _parent_dispatching_one_of_each(
        task_tool,
        tcid_self=tcid_self,
        tcid_mw=tcid_mw,
        checkpointer=checkpointer,
    )
    config: dict = {
        "configurable": {"thread_id": "mixed-parallel"},
        "recursion_limit": 100,
    }
    await parent.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    paused = await parent.aget_state(config)
    assert len(paused.interrupts) == 2, (
        "fixture broken: expected one paused interrupt per approval kind"
    )

    # Both interrupts must speak the same wire shape — the whole point of
    # the unification. If either one regresses to the legacy SurfSense shape
    # ``collect_pending_tool_calls`` would silently skip it and the count
    # below would be 1.
    pending = collect_pending_tool_calls(paused)
    assert dict(pending) == {tcid_self: 1, tcid_mw: 1}, (
        f"REGRESSION: not all interrupt kinds reached the routing layer; "
        f"got {pending!r}"
    )

    # Verify the actual wire payloads carry the LC HITL standard fields
    # (extra defensive assertion against partial regressions where one
    # path stamps tool_call_id but reverts the body shape).
    interrupt_types = {i.value.get("interrupt_type") for i in paused.interrupts}
    assert interrupt_types == {"gmail_email_send", "permission_ask"}

    # Resume order: same order the SSE stream would emit (interrupts list).
    decision_self = {"type": "approve"}
    decision_mw = {"type": "approve_always"}
    flat_decisions = [
        # Match `pending` order.
        decision_self if pending[0][0] == tcid_self else decision_mw,
        decision_mw if pending[0][0] == tcid_self else decision_self,
    ]
    by_tool_call_id = slice_decisions_by_tool_call(flat_decisions, pending)
    lg_resume_map = build_lg_resume_map(paused, by_tool_call_id)
    assert len(lg_resume_map) == 2

    config["configurable"]["surfsense_resume_value"] = by_tool_call_id
    await parent.ainvoke(Command(resume=lg_resume_map), config)

    final = await parent.aget_state(config)
    assert not final.interrupts, (
        f"expected both branches resumed, but state still has interrupts: "
        f"{final.interrupts!r}"
    )

    # Each subagent must have received its own slice — verify by inspecting
    # the JSON-serialized result messages.
    payloads: list[dict] = []
    for msg in final.values.get("messages", []) or []:
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            with contextlib.suppress(json.JSONDecodeError):
                payloads.append(json.loads(content))

    self_payloads = [p for p in payloads if p.get("kind") == "self_gated"]
    mw_payloads = [p for p in payloads if p.get("kind") == "middleware_gated"]
    assert len(self_payloads) == 1, (
        f"self-gated subagent did not complete; payloads: {payloads!r}"
    )
    assert len(mw_payloads) == 1, (
        f"middleware-gated subagent did not complete; payloads: {payloads!r}"
    )

    # Self-gated approve → HITLResult(decision_type="approve", rejected=False).
    assert self_payloads[0]["decision_type"] == "approve"
    assert self_payloads[0]["rejected"] is False

    # Middleware-gated approve_always → canonical permission shape unchanged.
    assert mw_payloads[0]["decision"] == {"decision_type": "approve_always"}
