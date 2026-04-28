"""Smoke test: scripted harness drives create_agent end-to-end and produces a tool-call-then-final-text trace."""

from __future__ import annotations

import pytest
from langchain.agents import create_agent

from tests.integration.harness import (
    ScriptedTurn,
    StubToolSpec,
    build_scripted_harness,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_scripted_harness_drives_basic_agent() -> None:
    harness = build_scripted_harness(
        turns=[
            ScriptedTurn(
                tool_calls=[
                    {"name": "echo", "args": {"x": 1}, "id": "call_1"},
                ]
            ),
            ScriptedTurn(text="done"),
        ],
        tools=[
            StubToolSpec(
                name="echo",
                description="Echo args back.",
                handler=lambda **kwargs: {"echoed": kwargs},
            ),
        ],
    )

    agent = create_agent(
        harness.model,
        system_prompt="You are a test agent.",
        tools=harness.tools,
    )

    result = await agent.ainvoke({"messages": [("user", "do the thing")]})
    messages = result["messages"]
    final_ai = next(
        (m for m in reversed(messages) if m.__class__.__name__ == "AIMessage"),
        None,
    )
    assert final_ai is not None
    assert final_ai.content == "done"
    tool_messages = [m for m in messages if m.__class__.__name__ == "ToolMessage"]
    assert len(tool_messages) == 1
    assert "echoed" in str(tool_messages[0].content)
