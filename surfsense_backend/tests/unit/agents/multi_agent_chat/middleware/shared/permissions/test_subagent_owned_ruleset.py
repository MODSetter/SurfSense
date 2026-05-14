"""Regression: subagent-owned rulesets layer cleanly into ``PermissionMiddleware``.

The KB unification swap (legacy ``interrupt_on`` map → KB-owned ``Ruleset``
threaded through ``build_permission_mw(extra_rulesets=...)``) must produce
*exactly one* interrupt per destructive FS call, in LC HITL shape, even
when ``enable_permission`` is False — destructive ops always ask.

We exercise the production factory and a real ``PermissionMiddleware`` on a
real ``StateGraph`` so the test catches regressions in factory gating,
ruleset layering, and interrupt emission together.
"""

from __future__ import annotations

from typing import Annotated, Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command
from typing_extensions import TypedDict

from app.agents.multi_agent_chat.middleware.shared.permissions import (
    build_permission_mw,
)
from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.permissions import Rule, Ruleset


def _kb_style_ruleset() -> Ruleset:
    """Mirror :data:`knowledge_base.agent.KB_RULESET` without importing it.

    Importing the agent module pulls in deepagents and prompts; this test
    is about the factory + middleware contract, not KB wiring.
    """
    return Ruleset(
        origin="knowledge_base",
        rules=[
            Rule(permission="rm", pattern="*", action="ask"),
            Rule(permission="rmdir", pattern="*", action="ask"),
            Rule(permission="move_file", pattern="*", action="ask"),
            Rule(permission="edit_file", pattern="*", action="ask"),
            Rule(permission="write_file", pattern="*", action="ask"),
        ],
    )


class _State(TypedDict, total=False):
    messages: Annotated[list, add_messages]


def _build_graph_with_permission_middleware(
    *,
    flags: AgentFeatureFlags,
    extra_rulesets: list[Ruleset] | None,
    checkpointer: InMemorySaver,
):
    """Compile a one-node graph that emits a tool call for ``rm`` and
    routes through the production ``PermissionMiddleware``.

    The node returns an ``AIMessage`` with a tool call. The middleware's
    ``after_model`` hook intercepts and (if a rule says ``ask``) raises
    a ``GraphInterrupt`` carrying the LC HITL payload.
    """
    pm = build_permission_mw(flags=flags, extra_rulesets=extra_rulesets)

    def node(_state: _State) -> dict[str, Any]:
        msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "rm",
                    "args": {"path": "/tmp/foo"},
                    "id": "call-rm-1",
                    "type": "tool_call",
                }
            ],
        )
        return {"messages": [msg]}

    def after_node(state: _State) -> dict[str, Any] | None:
        if pm is None:
            return None
        # PermissionMiddleware._process ignores runtime; the test never relies
        # on the runtime context, so passing None keeps the harness lean.
        return pm._process(state, None)  # type: ignore[arg-type]

    g = StateGraph(_State)
    g.add_node("emit", node)
    g.add_node("permission", after_node)
    g.add_edge(START, "emit")
    g.add_edge("emit", "permission")
    g.add_edge("permission", END)
    return g.compile(checkpointer=checkpointer), pm


@pytest.mark.asyncio
async def test_kb_ruleset_raises_one_lc_hitl_ask_for_rm_even_when_permission_flag_off():
    """KB ruleset: ``rm`` must ask once even with ``enable_permission=False``.

    This is the keystone of the unification: the legacy ``interrupt_on``
    map fired regardless of ``enable_permission``, so the migrated rules
    must too. Otherwise users could opt out of "ask before rm".
    """
    flags = AgentFeatureFlags(enable_permission=False)
    checkpointer = InMemorySaver()
    graph, pm = _build_graph_with_permission_middleware(
        flags=flags,
        extra_rulesets=[_kb_style_ruleset()],
        checkpointer=checkpointer,
    )
    assert pm is not None, "extras must force the middleware on"

    config = {"configurable": {"thread_id": "kb-cloud-rm"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    snap = await graph.aget_state(config)
    assert len(snap.interrupts) == 1, (
        f"REGRESSION: KB ruleset should raise exactly one interrupt; got "
        f"{[i.value for i in snap.interrupts]!r}"
    )
    payload = snap.interrupts[0].value
    requests = payload.get("action_requests")
    assert requests == [{"name": "rm", "args": {"path": "/tmp/foo"}}], (
        f"interrupt must carry the rm call in LC HITL shape; got {payload!r}"
    )
    assert payload.get("interrupt_type") == "permission_ask"


@pytest.mark.asyncio
async def test_kb_ruleset_resume_with_approve_lets_rm_through():
    """Resume with ``approve`` → call kept; the model continues normally."""
    flags = AgentFeatureFlags(enable_permission=False)
    checkpointer = InMemorySaver()
    graph, _ = _build_graph_with_permission_middleware(
        flags=flags,
        extra_rulesets=[_kb_style_ruleset()],
        checkpointer=checkpointer,
    )
    config = {"configurable": {"thread_id": "kb-cloud-rm-approve"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    await graph.ainvoke(
        Command(resume={"decisions": [{"type": "approve"}]}), config
    )
    final = await graph.aget_state(config)
    assert final.next == (), "graph must complete after approve"
    last_ai = next(
        (m for m in reversed(final.values["messages"]) if isinstance(m, AIMessage)),
        None,
    )
    assert last_ai is not None
    assert [tc["name"] for tc in last_ai.tool_calls] == ["rm"], (
        "approved rm call must remain on the AIMessage so the tool can run"
    )


@pytest.mark.asyncio
async def test_no_extras_with_permission_off_skips_middleware_entirely():
    """No extras + permission off → factory returns ``None`` (no engine).

    The legacy gating is preserved when no caller asks for rules: nothing
    runs, nothing pauses.
    """
    flags = AgentFeatureFlags(enable_permission=False)
    pm = build_permission_mw(flags=flags, extra_rulesets=None)
    assert pm is None
