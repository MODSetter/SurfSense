"""``approve_always`` decisions for MCP tools are saved via the trusted-tool saver."""

from __future__ import annotations

from typing import Annotated, Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command
from pydantic import BaseModel
from typing_extensions import TypedDict

from app.agents.multi_agent_chat.middleware.shared.permissions import (
    build_permission_mw,
)
from app.agents.shared.feature_flags import AgentFeatureFlags
from app.agents.new_chat.permissions import Rule, Ruleset


class _NoArgs(BaseModel):
    pass


async def _noop(**_kwargs) -> str:
    return ""


def _ask_rule(tool_name: str) -> Rule:
    return Rule(permission=tool_name, pattern="*", action="ask")


def _make_mcp_tool(*, name: str, connector_id: int):
    return StructuredTool(
        name=name,
        description=f"Run {name} via MCP.",
        coroutine=_noop,
        args_schema=_NoArgs,
        metadata={
            "mcp_connector_id": connector_id,
            "mcp_connector_name": "Linear",
            "mcp_transport": "http",
            "hitl": True,
        },
    )


def _make_native_tool(*, name: str):
    return StructuredTool(
        name=name,
        description=f"Native {name}.",
        coroutine=_noop,
        args_schema=_NoArgs,
        metadata={"hitl": True},
    )


class _State(TypedDict, total=False):
    messages: Annotated[list, add_messages]


def _build_graph(pm, tool_name: str):
    def emit(_state: _State) -> dict[str, Any]:
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": tool_name,
                            "args": {},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        }

    g = StateGraph(_State)
    g.add_node("emit", emit)
    g.add_node("permission", pm.aafter_model)  # type: ignore[arg-type]
    g.add_edge(START, "emit")
    g.add_edge("emit", "permission")
    g.add_edge("permission", END)
    return g.compile(checkpointer=InMemorySaver())


@pytest.mark.asyncio
async def test_approve_always_decision_saves_mcp_tool_via_callback():
    saved: list[tuple[int, str]] = []

    async def trusted_tool_saver(connector_id: int, tool_name: str) -> None:
        saved.append((connector_id, tool_name))

    tool = _make_mcp_tool(name="linear_create_issue", connector_id=7)
    pm = build_permission_mw(
        flags=AgentFeatureFlags(enable_permission=False),
        subagent_rulesets=[Ruleset(origin="linear", rules=[_ask_rule(tool.name)])],
        tools=[tool],
        trusted_tool_saver=trusted_tool_saver,
    )
    assert pm is not None

    graph = _build_graph(pm, tool.name)
    config = {"configurable": {"thread_id": "approve-always-mcp"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)
    await graph.ainvoke(
        Command(resume={"decisions": [{"type": "approve_always"}]}), config
    )

    assert saved == [(7, "linear_create_issue")]


@pytest.mark.asyncio
async def test_once_decision_does_not_save():
    saved: list[tuple[int, str]] = []

    async def trusted_tool_saver(connector_id: int, tool_name: str) -> None:
        saved.append((connector_id, tool_name))

    tool = _make_mcp_tool(name="linear_create_issue", connector_id=7)
    pm = build_permission_mw(
        flags=AgentFeatureFlags(enable_permission=False),
        subagent_rulesets=[Ruleset(origin="linear", rules=[_ask_rule(tool.name)])],
        tools=[tool],
        trusted_tool_saver=trusted_tool_saver,
    )
    assert pm is not None

    graph = _build_graph(pm, tool.name)
    config = {"configurable": {"thread_id": "once-mcp"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)
    await graph.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), config)

    assert saved == []


@pytest.mark.asyncio
async def test_approve_always_decision_for_native_tool_skips_save():
    """Native tools have no ``mcp_connector_id`` so there is nowhere to persist trust."""
    saved: list[tuple[int, str]] = []

    async def trusted_tool_saver(connector_id: int, tool_name: str) -> None:
        saved.append((connector_id, tool_name))

    tool = _make_native_tool(name="rm")
    pm = build_permission_mw(
        flags=AgentFeatureFlags(enable_permission=False),
        subagent_rulesets=[Ruleset(origin="kb", rules=[_ask_rule(tool.name)])],
        tools=[tool],
        trusted_tool_saver=trusted_tool_saver,
    )
    assert pm is not None

    graph = _build_graph(pm, tool.name)
    config = {"configurable": {"thread_id": "approve-always-native"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)
    await graph.ainvoke(
        Command(resume={"decisions": [{"type": "approve_always"}]}), config
    )

    assert saved == []


@pytest.mark.asyncio
async def test_approve_always_decision_with_no_saver_callback_is_a_noop():
    """Anonymous turns build the middleware without a ``trusted_tool_saver``; must not crash."""
    tool = _make_mcp_tool(name="linear_create_issue", connector_id=7)
    pm = build_permission_mw(
        flags=AgentFeatureFlags(enable_permission=False),
        subagent_rulesets=[Ruleset(origin="linear", rules=[_ask_rule(tool.name)])],
        tools=[tool],
        trusted_tool_saver=None,
    )
    assert pm is not None

    graph = _build_graph(pm, tool.name)
    config = {"configurable": {"thread_id": "anon-approve-always"}}
    await graph.ainvoke({"messages": [HumanMessage(content="seed")]}, config)
    await graph.ainvoke(
        Command(resume={"decisions": [{"type": "approve_always"}]}), config
    )
