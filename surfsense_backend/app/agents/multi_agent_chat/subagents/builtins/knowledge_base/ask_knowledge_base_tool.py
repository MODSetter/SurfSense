"""Wrap the read-only knowledge_base runnable as the ``ask_knowledge_base`` tool."""

from __future__ import annotations

from typing import Annotated

from langchain.tools import BaseTool, ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import StructuredTool
from langgraph.types import Command

from app.agents.multi_agent_chat.main_agent.middleware.checkpointed_subagent_middleware.config import (
    subagent_invoke_config,
)
from app.agents.multi_agent_chat.main_agent.middleware.checkpointed_subagent_middleware.constants import (
    EXCLUDED_STATE_KEYS,
)

from .prompts import load_readonly_description

TOOL_NAME = "ask_knowledge_base"


def _forward_state(runtime: ToolRuntime, query: str) -> dict:
    forwarded = {k: v for k, v in runtime.state.items() if k not in EXCLUDED_STATE_KEYS}
    forwarded["messages"] = [HumanMessage(content=query)]
    return forwarded


def _wrap_result(result: dict, tool_call_id: str) -> Command:
    messages = result.get("messages") or []
    if not messages:
        raise ValueError(
            "knowledge_base_readonly returned an empty 'messages' list; "
            "expected at least one assistant message."
        )
    last_text = (getattr(messages[-1], "text", None) or "").rstrip()
    return Command(
        update={"messages": [ToolMessage(last_text, tool_call_id=tool_call_id)]}
    )


def build_ask_knowledge_base_tool(kb_readonly_runnable: Runnable) -> BaseTool:
    def ask_knowledge_base(
        query: Annotated[
            str,
            "Full question for the workspace specialist. Include all path hints, "
            "filters, and constraints the specialist needs to answer.",
        ],
        runtime: ToolRuntime,
    ) -> str | Command:
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for ask_knowledge_base")
        sub_state = _forward_state(runtime, query)
        sub_config = subagent_invoke_config(runtime)
        result = kb_readonly_runnable.invoke(sub_state, config=sub_config)
        return _wrap_result(result, runtime.tool_call_id)

    async def aask_knowledge_base(
        query: Annotated[
            str,
            "Full question for the workspace specialist. Include all path hints, "
            "filters, and constraints the specialist needs to answer.",
        ],
        runtime: ToolRuntime,
    ) -> str | Command:
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID is required for ask_knowledge_base")
        sub_state = _forward_state(runtime, query)
        sub_config = subagent_invoke_config(runtime)
        result = await kb_readonly_runnable.ainvoke(sub_state, config=sub_config)
        return _wrap_result(result, runtime.tool_call_id)

    return StructuredTool.from_function(
        name=TOOL_NAME,
        func=ask_knowledge_base,
        coroutine=aask_knowledge_base,
        description=load_readonly_description(),
    )
