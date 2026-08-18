"""``task`` returns a model-readable error when no tool runtime is injected.

A truncated/mangled tool call can reach the ``task`` closure without LangChain
injecting ``ToolRuntime`` (``runtime is None``). Both the sync and async paths
must degrade to a ToolMessage-able string instead of raising ``AttributeError``
on ``runtime.tool_call_id`` and killing the turn.
"""

from __future__ import annotations

import pytest
from langchain_core.runnables import RunnableLambda

from app.agents.chat.multi_agent_chat.main_agent.middleware.checkpointed_subagent_middleware.task_tool import (
    build_task_tool_with_parent_config,
)

pytestmark = pytest.mark.unit


def _tool():
    sub = RunnableLambda(lambda s: {"messages": []})
    # workspace_id=None so the async path's spawn-paused check bypasses Redis.
    return build_task_tool_with_parent_config(
        [{"name": "alpha", "description": "alpha", "runnable": sub}],
        workspace_id=None,
    )


def test_sync_missing_runtime_returns_error_string() -> None:
    out = _tool().func(description="x", subagent_type="alpha", runtime=None)

    assert isinstance(out, str)
    assert "runtime" in out.lower()


@pytest.mark.asyncio
async def test_async_missing_runtime_returns_error_string() -> None:
    out = await _tool().coroutine(description="x", subagent_type="alpha", runtime=None)

    assert isinstance(out, str)
    assert "runtime" in out.lower()
