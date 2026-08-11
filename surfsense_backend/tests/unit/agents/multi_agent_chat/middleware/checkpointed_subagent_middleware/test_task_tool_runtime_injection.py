"""``ToolRuntime`` must be injected into ``task`` through the real ToolNode.

Regression guard for the custom ``args_schema``: if the schema omits the
directly-injected ``runtime`` field, pydantic validation silently drops the
ToolNode-injected runtime and every ``task`` call fails with ``runtime=None``.
This drives the tool exactly as the agent does (StateGraph + ToolNode) and
asserts the subagent actually runs.
"""

from __future__ import annotations

from typing import Annotated

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from app.agents.chat.multi_agent_chat.main_agent.middleware.checkpointed_subagent_middleware.task_tool import (
    build_task_tool_with_parent_config,
)

pytestmark = pytest.mark.unit


class _S(TypedDict):
    messages: Annotated[list, add_messages]


def _tool():
    sub = RunnableLambda(lambda s: {"messages": [AIMessage(content="KB ran.")]})
    return build_task_tool_with_parent_config(
        [{"name": "knowledge_base", "description": "kb", "runnable": sub}],
        workspace_id=1,
    )


@pytest.mark.asyncio
async def test_runtime_is_injected_and_subagent_runs() -> None:
    tool = _tool()
    g = StateGraph(_S)
    g.add_node("tools", ToolNode([tool]))
    g.add_edge(START, "tools")
    g.add_edge("tools", END)
    app = g.compile()

    ai = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "task",
                "args": {"description": "x", "subagent_type": "knowledge_base"},
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )
    out = await app.ainvoke({"messages": [ai]})

    # If runtime were dropped, the tool returns the "could not read the tool
    # runtime" guard string instead of the subagent's output.
    assert "KB ran." in str(out["messages"][-1].content)


def test_runtime_stays_out_of_model_facing_schema() -> None:
    props = convert_to_openai_tool(_tool())["function"]["parameters"]["properties"]

    assert "runtime" not in props
