"""End-to-end resume-bridge tests against a real LangGraph subagent."""

from __future__ import annotations

import ast
import asyncio
from types import SimpleNamespace

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.config import (
    subagent_invoke_config,
)
from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.resume_routing import (
    collect_pending_tool_calls,
    slice_decisions_by_tool_call,
)
from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.task_tool import (
    build_task_tool_with_parent_config,
)


class _SubagentState(TypedDict, total=False):
    messages: list
    decision_text: str


def _build_single_interrupt_subagent():
    def approve_node(state):
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


def _make_runtime(config: dict, *, tool_call_id: str = "parent-tcid-1") -> ToolRuntime:
    return ToolRuntime(
        state={"messages": [HumanMessage(content="seed")]},
        context=None,
        config=config,
        stream_writer=None,
        tool_call_id=tool_call_id,
        store=None,
    )


def _prime_subagent_at_runtime_thread(subagent, runtime: ToolRuntime) -> dict:
    """Build the per-call ``RunnableConfig`` the production ``task`` tool will use.

    Mirrors what the ``task`` tool does on first invocation so test fixtures
    can prime the subagent's pending interrupt at the same checkpoint slot
    (per-call ``thread_id``) the bridge looks at on resume.
    """
    return subagent_invoke_config(runtime)


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
    runtime = _make_runtime(parent_config)
    sub_config = _prime_subagent_at_runtime_thread(subagent, runtime)
    await subagent.ainvoke({"messages": [HumanMessage(content="seed")]}, sub_config)
    snap = await subagent.aget_state(sub_config)
    assert snap.tasks and snap.tasks[0].interrupts, (
        "fixture broken: subagent should be paused on its interrupt"
    )

    parent_config["configurable"]["surfsense_resume_value"] = {
        runtime.tool_call_id: {"decisions": ["APPROVED"]}
    }

    result = await task_tool.coroutine(
        description="please approve",
        subagent_type="approver",
        runtime=runtime,
    )

    assert isinstance(result, Command)
    update = result.update
    assert update["decision_text"] == repr({"decisions": ["APPROVED"]})
    assert "surfsense_resume_value" not in parent_config["configurable"]

    final = await subagent.aget_state(sub_config)
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
    runtime = _make_runtime(parent_config)
    sub_config = _prime_subagent_at_runtime_thread(subagent, runtime)
    await subagent.ainvoke({"messages": [HumanMessage(content="seed")]}, sub_config)
    snap = await subagent.aget_state(sub_config)
    assert snap.tasks and snap.tasks[0].interrupts, "fixture broken"

    with pytest.raises(RuntimeError, match="resume bridge is broken"):
        await task_tool.coroutine(
            description="please approve",
            subagent_type="approver",
            runtime=runtime,
        )


def _build_bundle_subagent():
    def bundle_node(state):
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
    runtime = _make_runtime(parent_config)
    sub_config = _prime_subagent_at_runtime_thread(subagent, runtime)
    await subagent.ainvoke({"messages": [HumanMessage(content="seed")]}, sub_config)

    decisions_payload = {
        "decisions": [
            {"type": "approve", "args": {}},
            {"type": "edit", "args": {"args": {"name": "edited-b"}}},
            {"type": "reject", "args": {"message": "no thanks"}},
        ]
    }
    parent_config["configurable"]["surfsense_resume_value"] = {
        runtime.tool_call_id: decisions_payload
    }

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


@pytest.mark.asyncio
async def test_parallel_atask_routes_each_decision_to_its_own_subagent():
    """Two ``atask`` calls with distinct ``tool_call_id``s must each get their own decision.

    With per-call ``thread_id`` isolation and per-call resume keying, A's
    decision must reach A's pending interrupt and B's must reach B's. They
    must NOT cross-contaminate even though they share ``configurable``.
    """
    subagent_a = _build_single_interrupt_subagent()
    subagent_b = _build_single_interrupt_subagent()
    task_tool = build_task_tool_with_parent_config(
        [
            {
                "name": "approver_a",
                "description": "approves A",
                "runnable": subagent_a,
            },
            {
                "name": "approver_b",
                "description": "approves B",
                "runnable": subagent_b,
            },
        ]
    )

    parent_config: dict = {
        "configurable": {"thread_id": "parallel-thread"},
        "recursion_limit": 100,
    }

    runtime_a = _make_runtime(parent_config, tool_call_id="tcid-A")
    runtime_b = _make_runtime(parent_config, tool_call_id="tcid-B")

    sub_config_a = _prime_subagent_at_runtime_thread(subagent_a, runtime_a)
    sub_config_b = _prime_subagent_at_runtime_thread(subagent_b, runtime_b)

    await subagent_a.ainvoke(
        {"messages": [HumanMessage(content="seed-A")]}, sub_config_a
    )
    await subagent_b.ainvoke(
        {"messages": [HumanMessage(content="seed-B")]}, sub_config_b
    )

    parent_config["configurable"]["surfsense_resume_value"] = {
        "tcid-A": {"decisions": ["DECISION-A"]},
        "tcid-B": {"decisions": ["DECISION-B"]},
    }

    result_a, result_b = await asyncio.gather(
        task_tool.coroutine(
            description="please approve A",
            subagent_type="approver_a",
            runtime=runtime_a,
        ),
        task_tool.coroutine(
            description="please approve B",
            subagent_type="approver_b",
            runtime=runtime_b,
        ),
    )

    assert isinstance(result_a, Command)
    assert isinstance(result_b, Command)
    assert result_a.update["decision_text"] == repr({"decisions": ["DECISION-A"]})
    assert result_b.update["decision_text"] == repr({"decisions": ["DECISION-B"]})

    assert "surfsense_resume_value" not in parent_config["configurable"]


@pytest.mark.asyncio
async def test_full_resume_routing_glue_for_two_paused_subagents():
    """End-to-end: extractor + slicer + bridge correctly route a flat decisions list.

    This simulates exactly what ``stream_resume_chat`` will do on resume:
    given a paused parent state with two pending interrupts (one per
    subagent) and a flat ``decisions`` list, build the per-tool-call dict
    via ``collect_pending_tool_calls`` + ``slice_decisions_by_tool_call``,
    then resume the bridge concurrently and verify each subagent received
    only its own slice.
    """
    subagent_a = _build_bundle_subagent()
    subagent_b = _build_single_interrupt_subagent()
    task_tool = build_task_tool_with_parent_config(
        [
            {
                "name": "bundler",
                "description": "three-action bundle",
                "runnable": subagent_a,
            },
            {
                "name": "approver",
                "description": "single approval",
                "runnable": subagent_b,
            },
        ]
    )

    parent_config: dict = {
        "configurable": {"thread_id": "glue-thread"},
        "recursion_limit": 100,
    }

    runtime_a = _make_runtime(parent_config, tool_call_id="tcid-bundler")
    runtime_b = _make_runtime(parent_config, tool_call_id="tcid-approver")

    sub_config_a = _prime_subagent_at_runtime_thread(subagent_a, runtime_a)
    sub_config_b = _prime_subagent_at_runtime_thread(subagent_b, runtime_b)

    await subagent_a.ainvoke(
        {"messages": [HumanMessage(content="seed-A")]}, sub_config_a
    )
    await subagent_b.ainvoke(
        {"messages": [HumanMessage(content="seed-B")]}, sub_config_b
    )

    # Synthetic parent state mirroring what the parent's pregel would have
    # bundled: one Interrupt per subagent, value carrying tool_call_id +
    # action_requests (exactly the shape ``propagation.wrap_with_tool_call_id``
    # produces).
    parent_interrupts = (
        SimpleNamespace(
            id="i-bundler",
            value={
                "action_requests": [
                    {"name": "create_a", "args": {}, "description": ""},
                    {"name": "create_b", "args": {}, "description": ""},
                    {"name": "create_c", "args": {}, "description": ""},
                ],
                "review_configs": [{}, {}, {}],
                "tool_call_id": "tcid-bundler",
            },
        ),
        SimpleNamespace(
            id="i-approver",
            value={
                "action_requests": [{"name": "approve", "args": {}, "description": ""}],
                "review_configs": [{}],
                "tool_call_id": "tcid-approver",
            },
        ),
    )
    parent_state = SimpleNamespace(interrupts=parent_interrupts)

    flat_decisions = [
        {"type": "approve"},
        {"type": "edit", "args": {"args": {"name": "edited-b"}}},
        {"type": "reject", "args": {"message": "no thanks"}},
        {"type": "approve"},
    ]

    pending = collect_pending_tool_calls(parent_state)
    assert pending == [("tcid-bundler", 3), ("tcid-approver", 1)]

    routed = slice_decisions_by_tool_call(flat_decisions, pending)
    parent_config["configurable"]["surfsense_resume_value"] = routed

    result_a, result_b = await asyncio.gather(
        task_tool.coroutine(
            description="run bundle",
            subagent_type="bundler",
            runtime=runtime_a,
        ),
        task_tool.coroutine(
            description="please approve",
            subagent_type="approver",
            runtime=runtime_b,
        ),
    )

    assert isinstance(result_a, Command)
    assert isinstance(result_b, Command)

    received_a = ast.literal_eval(result_a.update["decision_text"])
    assert received_a == {"decisions": flat_decisions[0:3]}
    assert result_b.update["decision_text"] == repr({"decisions": flat_decisions[3:4]})

    assert "surfsense_resume_value" not in parent_config["configurable"]
