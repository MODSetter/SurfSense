"""Behavioural guarantees for parallel ``task`` tool calls (non-HITL cases).

The HITL bridge tests in ``test_hitl_bridge.py`` cover the parallel-interrupt
flow. This file covers the *normal* parallel paths (no interrupts) and the
failure-isolation guarantee — together they pin the behaviour we promise the
user about ``asyncio.gather`` over two ``atask`` coroutines.
"""

from __future__ import annotations

import asyncio

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from typing_extensions import TypedDict

from app.agents.chat.multi_agent_chat.main_agent.middleware.checkpointed_subagent_middleware.task_tool import (
    build_task_tool_with_parent_config,
)


class _SubState(TypedDict, total=False):
    messages: list


def _build_success_subagent(reply: str):
    """A subagent that completes immediately with ``reply``, never interrupts."""

    def node(_state):
        return {"messages": [AIMessage(content=reply)]}

    g = StateGraph(_SubState)
    g.add_node("only", node)
    g.add_edge(START, "only")
    g.add_edge("only", END)
    return g.compile(checkpointer=InMemorySaver())


def _build_failing_subagent(exc: Exception):
    """A subagent whose only node raises ``exc`` — simulates a tool-level failure."""

    def node(_state):
        raise exc

    g = StateGraph(_SubState)
    g.add_node("only", node)
    g.add_edge(START, "only")
    g.add_edge("only", END)
    return g.compile(checkpointer=InMemorySaver())


def _make_runtime(parent_config: dict, *, tool_call_id: str) -> ToolRuntime:
    return ToolRuntime(
        state={"messages": [HumanMessage(content="seed")]},
        context=None,
        config=parent_config,
        stream_writer=None,
        tool_call_id=tool_call_id,
        store=None,
    )


def _tool_message_text(cmd: Command, *, expected_tcid: str) -> str:
    """Return the ToolMessage content the task tool produced for ``expected_tcid``."""
    assert isinstance(cmd, Command), f"expected Command, got {type(cmd).__name__}"
    messages = cmd.update["messages"]
    assert len(messages) == 1, f"expected 1 ToolMessage, got {len(messages)}"
    msg = messages[0]
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == expected_tcid
    return msg.content


@pytest.mark.asyncio
async def test_two_parallel_atasks_to_different_subagents_both_succeed():
    """Normal happy-path: two distinct subagents complete in parallel without interrupting."""
    subagent_a = _build_success_subagent("A is done")
    subagent_b = _build_success_subagent("B is done")
    task_tool = build_task_tool_with_parent_config(
        [
            {"name": "alpha", "description": "alpha agent", "runnable": subagent_a},
            {"name": "beta", "description": "beta agent", "runnable": subagent_b},
        ]
    )

    parent_config: dict = {
        "configurable": {"thread_id": "ok-thread"},
        "recursion_limit": 100,
    }
    runtime_a = _make_runtime(parent_config, tool_call_id="tcid-A")
    runtime_b = _make_runtime(parent_config, tool_call_id="tcid-B")

    result_a, result_b = await asyncio.gather(
        task_tool.coroutine(
            description="do A",
            subagent_type="alpha",
            runtime=runtime_a,
        ),
        task_tool.coroutine(
            description="do B",
            subagent_type="beta",
            runtime=runtime_b,
        ),
    )

    assert _tool_message_text(result_a, expected_tcid="tcid-A") == "A is done"
    assert _tool_message_text(result_b, expected_tcid="tcid-B") == "B is done"


@pytest.mark.asyncio
async def test_two_parallel_atasks_same_subagent_type_different_tool_call_ids():
    """Per-call ``thread_id`` isolation: same compiled subagent invoked twice in parallel.

    Both calls share the same ``InMemorySaver`` instance but are namespaced by
    distinct ``tool_call_id``s, so checkpoints land in disjoint thread slots.
    """
    shared_subagent = _build_success_subagent("ok")
    task_tool = build_task_tool_with_parent_config(
        [
            {
                "name": "approver",
                "description": "shared approver",
                "runnable": shared_subagent,
            },
        ]
    )

    parent_config: dict = {
        "configurable": {"thread_id": "shared-subagent-thread"},
        "recursion_limit": 100,
    }
    runtime_a = _make_runtime(parent_config, tool_call_id="tcid-A")
    runtime_b = _make_runtime(parent_config, tool_call_id="tcid-B")

    result_a, result_b = await asyncio.gather(
        task_tool.coroutine(
            description="first request",
            subagent_type="approver",
            runtime=runtime_a,
        ),
        task_tool.coroutine(
            description="second request",
            subagent_type="approver",
            runtime=runtime_b,
        ),
    )

    # Both calls succeed and produce ToolMessages keyed by their own tool_call_id.
    assert _tool_message_text(result_a, expected_tcid="tcid-A") == "ok"
    assert _tool_message_text(result_b, expected_tcid="tcid-B") == "ok"

    # Verify checkpoint isolation: each call's state lives at its own thread_id.
    state_a = await shared_subagent.aget_state(
        {"configurable": {"thread_id": "shared-subagent-thread::task:tcid-A"}}
    )
    state_b = await shared_subagent.aget_state(
        {"configurable": {"thread_id": "shared-subagent-thread::task:tcid-B"}}
    )
    assert state_a.values["messages"][-1].content == "ok"
    assert state_b.values["messages"][-1].content == "ok"

    # The parent's own thread_id slot is untouched by either subagent.
    state_parent = await shared_subagent.aget_state(
        {"configurable": {"thread_id": "shared-subagent-thread"}}
    )
    assert state_parent.values == {} or state_parent.values.get("messages") in (
        None,
        [],
    )


@pytest.mark.asyncio
async def test_one_atask_failure_does_not_corrupt_sibling_atask():
    """Failure isolation: a sibling's exception must not poison the surviving atask's state.

    Note: in production, langgraph's pregel runner cancels siblings when any
    parallel task raises a non-``GraphBubbleUp`` exception (see
    ``_should_stop_others`` in ``langgraph/pregel/_runner.py``). At our layer
    that policy is invisible — what we *can* guarantee is that the two atask
    coroutines have disjoint state, so the surviving one returns a valid
    Command even when its sibling explodes.
    """
    failing_subagent = _build_failing_subagent(ValueError("boom"))
    surviving_subagent = _build_success_subagent("still here")
    task_tool = build_task_tool_with_parent_config(
        [
            {
                "name": "broken",
                "description": "always fails",
                "runnable": failing_subagent,
            },
            {
                "name": "healthy",
                "description": "always succeeds",
                "runnable": surviving_subagent,
            },
        ]
    )

    parent_config: dict = {
        "configurable": {"thread_id": "iso-thread"},
        "recursion_limit": 100,
    }
    runtime_fail = _make_runtime(parent_config, tool_call_id="tcid-fail")
    runtime_ok = _make_runtime(parent_config, tool_call_id="tcid-ok")

    results = await asyncio.gather(
        task_tool.coroutine(
            description="will explode",
            subagent_type="broken",
            runtime=runtime_fail,
        ),
        task_tool.coroutine(
            description="will work",
            subagent_type="healthy",
            runtime=runtime_ok,
        ),
        return_exceptions=True,
    )

    fail_result, ok_result = results

    assert isinstance(fail_result, Exception), (
        f"expected the broken subagent to raise, got {fail_result!r}"
    )
    # ValueError gets wrapped in langgraph's internal exception types — the
    # important guarantee is "this path errored", not the specific class.
    assert "boom" in str(fail_result) or isinstance(fail_result, ValueError)

    assert _tool_message_text(ok_result, expected_tcid="tcid-ok") == "still here"

    # Configurable side-channel must not have been corrupted by the failure.
    assert "surfsense_resume_value" not in parent_config["configurable"]
