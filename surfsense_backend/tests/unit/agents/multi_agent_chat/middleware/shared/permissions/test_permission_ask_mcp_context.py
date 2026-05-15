"""Permission-ask payload surfaces tool metadata for the FE card."""

from __future__ import annotations

from typing import Annotated, Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict

from app.agents.multi_agent_chat.middleware.shared.permissions import (
    build_permission_mw,
)
from app.agents.multi_agent_chat.middleware.shared.permissions.ask.payload import (
    build_permission_ask_payload,
)
from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.permissions import Rule, Ruleset


class _NoArgs(BaseModel):
    pass


async def _noop(**_kwargs) -> str:
    return ""


def _ask_rule(tool_name: str) -> Rule:
    return Rule(permission=tool_name, pattern="*", action="ask")


def _make_mcp_tool(*, name: str, connector_id: int, connector_name: str):
    return StructuredTool(
        name=name,
        description=f"Run {name} via MCP.",
        coroutine=_noop,
        args_schema=_NoArgs,
        metadata={
            "mcp_connector_id": connector_id,
            "mcp_connector_name": connector_name,
            "mcp_transport": "http",
            "hitl": True,
        },
    )


def test_payload_surfaces_mcp_fields_from_tool():
    tool = _make_mcp_tool(
        name="linear_create_issue", connector_id=42, connector_name="Linear (acme)"
    )
    payload = build_permission_ask_payload(
        tool_name=tool.name,
        args={"title": "bug"},
        patterns=[tool.name],
        rules=[_ask_rule(tool.name)],
        tool=tool,
    )
    ctx = payload["context"]
    assert ctx["mcp_connector_id"] == 42
    assert ctx["mcp_server"] == "Linear (acme)"
    assert ctx["tool_description"] == "Run linear_create_issue via MCP."


def test_payload_omits_tool_fields_when_tool_is_none():
    payload = build_permission_ask_payload(
        tool_name="rm",
        args={"path": "/tmp/x"},
        patterns=["rm"],
        rules=[_ask_rule("rm")],
        tool=None,
    )
    ctx = payload["context"]
    assert "mcp_connector_id" not in ctx
    assert "mcp_server" not in ctx
    assert "tool_description" not in ctx


def test_palette_includes_approve_always_for_mcp_tool():
    """Saving to the connector's trusted-tools list is only possible for MCP tools."""
    tool = _make_mcp_tool(
        name="linear_create_issue", connector_id=42, connector_name="Linear"
    )
    palette = build_permission_ask_payload(
        tool_name=tool.name,
        args={},
        patterns=[tool.name],
        rules=[_ask_rule(tool.name)],
        tool=tool,
    )["review_configs"][0]["allowed_decisions"]
    assert "approve_always" in palette


def test_palette_excludes_approve_always_for_native_tool():
    """Native tools have no place to persist trust, so don't offer the button."""
    native = StructuredTool(
        name="rm",
        description="Remove a file.",
        coroutine=_noop,
        args_schema=_NoArgs,
        metadata={"hitl": True},
    )
    palette = build_permission_ask_payload(
        tool_name=native.name,
        args={"path": "/tmp/x"},
        patterns=[native.name],
        rules=[_ask_rule(native.name)],
        tool=native,
    )["review_configs"][0]["allowed_decisions"]
    assert "approve_always" not in palette
    assert palette == ["approve", "reject", "edit"]


def test_palette_excludes_approve_always_when_tool_is_none():
    """Without a tool object the middleware can't tell — fall back to the safe triad."""
    palette = build_permission_ask_payload(
        tool_name="rm",
        args={"path": "/tmp/x"},
        patterns=["rm"],
        rules=[_ask_rule("rm")],
        tool=None,
    )["review_configs"][0]["allowed_decisions"]
    assert palette == ["approve", "reject", "edit"]


def test_payload_omits_falsy_mcp_metadata_fields():
    tool = StructuredTool(
        name="anon_tool",
        description="",
        coroutine=_noop,
        args_schema=_NoArgs,
        metadata={"mcp_connector_id": None, "mcp_connector_name": ""},
    )
    ctx = build_permission_ask_payload(
        tool_name=tool.name,
        args={},
        patterns=[tool.name],
        rules=[_ask_rule(tool.name)],
        tool=tool,
    )["context"]
    assert "mcp_connector_id" not in ctx
    assert "mcp_server" not in ctx
    assert "tool_description" not in ctx


class _State(TypedDict, total=False):
    messages: Annotated[list, add_messages]


def _emit_tool_call(tool_name: str, args: dict[str, Any], call_id: str):
    def _node(_state: _State) -> dict[str, Any]:
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": tool_name,
                            "args": args,
                            "id": call_id,
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        }

    return _node


def _compile_graph_with(pm, tool_name: str, args: dict[str, Any], call_id: str):
    def after(state: _State) -> dict[str, Any] | None:
        return pm.after_model(state, None)  # type: ignore[arg-type]

    g = StateGraph(_State)
    g.add_node("emit", _emit_tool_call(tool_name, args, call_id))
    g.add_node("permission", after)
    g.add_edge(START, "emit")
    g.add_edge("emit", "permission")
    g.add_edge("permission", END)
    return g.compile(checkpointer=InMemorySaver())


@pytest.mark.asyncio
async def test_middleware_decorates_interrupt_with_mcp_tool_metadata():
    tool = _make_mcp_tool(
        name="linear_create_issue", connector_id=7, connector_name="Linear"
    )
    pm = build_permission_mw(
        flags=AgentFeatureFlags(enable_permission=False),
        subagent_rulesets=[
            Ruleset(origin="linear", rules=[_ask_rule(tool.name)]),
        ],
        tools=[tool],
    )
    assert pm is not None

    graph = _compile_graph_with(pm, tool.name, {"title": "bug"}, "call-1")
    config = {"configurable": {"thread_id": "linear-ask"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    snap = await graph.aget_state(config)
    assert len(snap.interrupts) == 1
    ctx = snap.interrupts[0].value["context"]
    assert ctx["mcp_connector_id"] == 7
    assert ctx["mcp_server"] == "Linear"
    assert ctx["tool_description"] == "Run linear_create_issue via MCP."


@pytest.mark.asyncio
async def test_middleware_without_tool_index_still_asks_without_tool_fields():
    pm = build_permission_mw(
        flags=AgentFeatureFlags(enable_permission=False),
        subagent_rulesets=[Ruleset(origin="kb", rules=[_ask_rule("rm")])],
    )
    assert pm is not None

    graph = _compile_graph_with(pm, "rm", {"path": "/tmp/foo"}, "call-rm")
    config = {"configurable": {"thread_id": "kb-rm"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)

    snap = await graph.aget_state(config)
    assert len(snap.interrupts) == 1
    ctx = snap.interrupts[0].value["context"]
    assert "mcp_connector_id" not in ctx
    assert "mcp_server" not in ctx
    assert "tool_description" not in ctx
