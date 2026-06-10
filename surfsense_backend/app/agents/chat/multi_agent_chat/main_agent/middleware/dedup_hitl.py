"""Drop duplicate HITL tool calls before execution.

When the LLM emits multiple calls to the same HITL tool with the same
primary argument (e.g. two ``delete_calendar_event("Doctor Appointment")``),
only the first call is kept. Non-HITL tools are never touched.

This runs in the ``after_model`` hook — **before** any tool executes — so
the duplicate call is stripped from the AIMessage that gets checkpointed.
That means it is also safe across LangGraph ``interrupt()`` boundaries:
the removed call will never appear on graph resume.

Dedup-key resolution order (read from each tool's own ``metadata``):

1. ``tool.metadata["dedup_key"]`` — callable mapping the args dict to a
   stable signature string. This is the canonical mechanism.
2. ``tool.metadata["hitl_dedup_key"]`` — string naming a primary arg;
   used by MCP / Composio tools that only expose a single key field.

A tool with no resolver from either path simply opts out of dedup.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.tools import BaseTool
from langgraph.runtime import Runtime

from app.agents.chat.multi_agent_chat.shared.middleware.dedup_tool_calls import (
    DedupResolver,
    wrap_dedup_key_by_arg_name,
)

logger = logging.getLogger(__name__)


class DedupHITLToolCallsMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Remove duplicate HITL tool calls from a single LLM response.

    Only the **first** occurrence of each ``(tool-name, dedup_key)``
    pair is kept; subsequent duplicates are silently dropped.

    The dedup-resolver map is built from two sources, in priority order:

    1. ``tool.metadata["dedup_key"]`` — callable that receives the args dict
       and returns a string signature. This is the canonical mechanism.
    2. ``tool.metadata["hitl_dedup_key"]`` — string with a primary arg
       name; primarily used by MCP / Composio tools.
    """

    tools = ()

    def __init__(self, *, agent_tools: list[Any] | None = None) -> None:
        self._resolvers: dict[str, DedupResolver] = {}

        for t in agent_tools or []:
            meta = getattr(t, "metadata", None) or {}
            callable_key = meta.get("dedup_key")
            if callable(callable_key):
                self._resolvers[t.name] = callable_key
                continue
            if meta.get("hitl") and meta.get("hitl_dedup_key"):
                self._resolvers[t.name] = wrap_dedup_key_by_arg_name(
                    meta["hitl_dedup_key"]
                )

    def after_model(
        self, state: AgentState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        return self._dedup(state, self._resolvers)

    async def aafter_model(
        self, state: AgentState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        return self._dedup(state, self._resolvers)

    @staticmethod
    def _dedup(
        state: AgentState,
        resolvers: dict[str, DedupResolver],
    ) -> dict[str, Any] | None:
        messages = state.get("messages")
        if not messages:
            return None

        last_msg = messages[-1]
        if last_msg.type != "ai" or not getattr(last_msg, "tool_calls", None):
            return None

        tool_calls: list[dict[str, Any]] = last_msg.tool_calls
        seen: set[tuple[str, str]] = set()
        deduped: list[dict[str, Any]] = []

        for tc in tool_calls:
            name = tc.get("name", "")
            resolver = resolvers.get(name)
            if resolver is not None:
                try:
                    arg_val = resolver(tc.get("args", {}) or {})
                except Exception:
                    logger.exception(
                        "Dedup resolver for tool %s raised; keeping call", name
                    )
                    deduped.append(tc)
                    continue
                key = (name, arg_val)
                if key in seen:
                    logger.info(
                        "Dedup: dropped duplicate HITL tool call %s(%s)",
                        name,
                        arg_val,
                    )
                    continue
                seen.add(key)
            deduped.append(tc)

        if len(deduped) == len(tool_calls):
            return None

        updated_msg = last_msg.model_copy(update={"tool_calls": deduped})
        return {"messages": [updated_msg]}


def build_dedup_hitl_mw(tools: Sequence[BaseTool]) -> DedupHITLToolCallsMiddleware:
    return DedupHITLToolCallsMiddleware(agent_tools=list(tools))
