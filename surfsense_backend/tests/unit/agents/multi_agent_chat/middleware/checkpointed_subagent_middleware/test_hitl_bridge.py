"""End-to-end resume-bridge tests against a real LangGraph subagent."""

from __future__ import annotations

import ast

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.task_tool import (
    build_task_tool_with_parent_config,
)


class _SubagentState(TypedDict, total=False):
    messages: list
    decision_text: str


def _build_single_interrupt_subagent():
    def approve_node(state):
        from langchain_core.messages import AIMessage

        decision = interrupt(
            {
                "action_requests": [
                    {
                        "name": "do_thing",
                        "args": {"x": 1},
                        "description": "test action",
                    }
                ],
                "review_configs": [{}],
            }
        )
        return {
            "messages": [AIMessage(content="done")],
            "decision_text": repr(decision),
        }

    graph = StateGraph(_SubagentState)
    graph.add_node("approve", approve_node)
    graph.add_edge(START, "approve")
    graph.add_edge("approve", END)
    return graph.compile(checkpointer=InMemorySaver())


def _make_runtime(config: dict) -> ToolRuntime:
    return ToolRuntime(
        state={"messages": [HumanMessage(content="seed")]},
        context=None,
        config=config,
        stream_writer=None,
        tool_call_id="parent-tcid-1",
        store=None,
    )


@pytest.mark.asyncio
async def test_resume_bridge_dispatches_decision_into_pending_subagent():
    """Side-channel decision must reach the subagent's pending interrupt verbatim."""
    subagent = _build_single_interrupt_subagent()
    task_tool = build_task_tool_with_parent_config(
        [
            {
                "name": "approver",
                "description": "approves things",
                "runnable": subagent,
            }
        ]
    )

    parent_config: dict = {
        "configurable": {"thread_id": "shared-thread"},
        "recursion_limit": 100,
    }
    await subagent.ainvoke({"messages": [HumanMessage(content="seed")]}, parent_config)
    snap = await subagent.aget_state(parent_config)
    assert snap.tasks and snap.tasks[0].interrupts, (
        "fixture broken: subagent should be paused on its interrupt"
    )

    parent_config["configurable"]["surfsense_resume_value"] = {
        "decisions": ["APPROVED"]
    }
    runtime = _make_runtime(parent_config)

    result = await task_tool.coroutine(
        description="please approve",
        subagent_type="approver",
        runtime=runtime,
    )

    assert isinstance(result, Command)
    update = result.update
    assert update["decision_text"] == repr({"decisions": ["APPROVED"]})
    assert "surfsense_resume_value" not in parent_config["configurable"]

    final = await subagent.aget_state(parent_config)
    assert not final.tasks or all(not t.interrupts for t in final.tasks)


@pytest.mark.asyncio
async def test_pending_interrupt_without_resume_value_raises_runtime_error():
    """Bridge must fail loud rather than silently replay the user's interrupt."""
    subagent = _build_single_interrupt_subagent()
    task_tool = build_task_tool_with_parent_config(
        [
            {
                "name": "approver",
                "description": "approves things",
                "runnable": subagent,
            }
        ]
    )

    parent_config: dict = {
        "configurable": {"thread_id": "guard-thread"},
        "recursion_limit": 100,
    }
    await subagent.ainvoke({"messages": [HumanMessage(content="seed")]}, parent_config)
    snap = await subagent.aget_state(parent_config)
    assert snap.tasks and snap.tasks[0].interrupts, "fixture broken"

    runtime = _make_runtime(parent_config)

    with pytest.raises(RuntimeError, match="resume bridge is broken"):
        await task_tool.coroutine(
            description="please approve",
            subagent_type="approver",
            runtime=runtime,
        )


def _build_bundle_subagent():
    def bundle_node(state):
        from langchain_core.messages import AIMessage

        decision = interrupt(
            {
                "action_requests": [
                    {"name": "create_a", "args": {}, "description": ""},
                    {"name": "create_b", "args": {}, "description": ""},
                    {"name": "create_c", "args": {}, "description": ""},
                ],
                "review_configs": [{}, {}, {}],
            }
        )
        return {
            "messages": [AIMessage(content="bundle-done")],
            "decision_text": repr(decision),
        }

    graph = StateGraph(_SubagentState)
    graph.add_node("bundle", bundle_node)
    graph.add_edge(START, "bundle")
    graph.add_edge("bundle", END)
    return graph.compile(checkpointer=InMemorySaver())


@pytest.mark.asyncio
async def test_bundle_three_mixed_decisions_arrive_in_order():
    """Approve / edit / reject for a 3-action bundle must land at ordinals 0/1/2."""
    subagent = _build_bundle_subagent()
    task_tool = build_task_tool_with_parent_config(
        [
            {
                "name": "bundler",
                "description": "creates a bundle",
                "runnable": subagent,
            }
        ]
    )

    parent_config: dict = {
        "configurable": {"thread_id": "bundle-thread"},
        "recursion_limit": 100,
    }
    await subagent.ainvoke({"messages": [HumanMessage(content="seed")]}, parent_config)

    decisions_payload = {
        "decisions": [
            {"type": "approve", "args": {}},
            {"type": "edit", "args": {"args": {"name": "edited-b"}}},
            {"type": "reject", "args": {"message": "no thanks"}},
        ]
    }
    parent_config["configurable"]["surfsense_resume_value"] = decisions_payload
    runtime = _make_runtime(parent_config)

    result = await task_tool.coroutine(
        description="run bundle",
        subagent_type="bundler",
        runtime=runtime,
    )

    assert isinstance(result, Command)
    received = ast.literal_eval(result.update["decision_text"])
    assert received == decisions_payload
    assert received["decisions"][0]["type"] == "approve"
    assert received["decisions"][1]["type"] == "edit"
    assert received["decisions"][1]["args"] == {"args": {"name": "edited-b"}}
    assert received["decisions"][2]["type"] == "reject"
