"""Wrap the read-only knowledge_base runnable as the ``ask_knowledge_base`` tool."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from langchain.tools import BaseTool, ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import StructuredTool
from langgraph.types import Command

from app.agents.chat.multi_agent_chat.subagents.shared.invocation import (
    EXCLUDED_STATE_KEYS,
    subagent_invoke_config,
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
    # Carry reducer-backed state (notably citation_registry, populated by the
    # read-only graph's search_knowledge_base call) back up to the caller so
    # [n] labels emitted via ask_knowledge_base resolve at turn end. Drop
    # ``messages`` — we synthesize our own ToolMessage — and anything the
    # subagent boundary excludes.
    forwarded_state = {
        k: v
        for k, v in result.items()
        if k not in EXCLUDED_STATE_KEYS and k != "messages"
    }
    return Command(
        update={
            **forwarded_state,
            "messages": [ToolMessage(last_text, tool_call_id=tool_call_id)],
        }
    )


def build_ask_knowledge_base_tool(
    kb_readonly: Runnable | Callable[[], Runnable],
) -> BaseTool:
    """Build the ``ask_knowledge_base`` tool backed by the read-only KB graph.

    ``kb_readonly`` may be a pre-compiled ``Runnable`` or a zero-arg factory
    that compiles it on first use. Passing a factory defers the ~0.3-0.8s
    ``create_agent`` cost of the read-only knowledge_base graph until a subagent
    actually calls ``ask_knowledge_base``, keeping it off the cold agent-build
    (time-to-first-token) path. The factory result is memoized.
    """
    _cache: dict[str, Runnable] = {}

    def _resolve() -> Runnable:
        if not callable(kb_readonly) or isinstance(kb_readonly, Runnable):
            return kb_readonly  # type: ignore[return-value]
        cached = _cache.get("runnable")
        if cached is None:
            cached = kb_readonly()
            _cache["runnable"] = cached
        return cached

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
        result = _resolve().invoke(sub_state, config=sub_config)
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
        result = await _resolve().ainvoke(sub_state, config=sub_config)
        return _wrap_result(result, runtime.tool_call_id)

    return StructuredTool.from_function(
        name=TOOL_NAME,
        func=ask_knowledge_base,
        coroutine=aask_knowledge_base,
        description=load_readonly_description(),
    )
