"""``ask_knowledge_base`` must self-correct, not crash the turn, on a bad call."""

from __future__ import annotations

import pytest
from langchain.tools import ToolRuntime

from app.agents.chat.multi_agent_chat.subagents.builtins.knowledge_base.ask_knowledge_base_tool import (
    build_ask_knowledge_base_tool,
)

pytestmark = pytest.mark.unit


def _runtime(tool_call_id: str) -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=None,
        config={},
        stream_writer=None,
        tool_call_id=tool_call_id,
        store=None,
    )


def test_missing_tool_call_id_returns_error_string() -> None:
    tool = build_ask_knowledge_base_tool(kb_readonly=lambda: None)

    result = tool.func("what is X?", _runtime(""))

    assert isinstance(result, str)
    assert "tool call id" in result.lower()


async def test_missing_tool_call_id_returns_error_string_async() -> None:
    tool = build_ask_knowledge_base_tool(kb_readonly=lambda: None)

    result = await tool.coroutine("what is X?", _runtime(""))

    assert isinstance(result, str)
    assert "tool call id" in result.lower()
