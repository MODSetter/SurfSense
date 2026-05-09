"""Drop duplicate HITL tool calls before execution."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.tools import BaseTool

from app.agents.new_chat.middleware import DedupHITLToolCallsMiddleware


def build_dedup_hitl_mw(tools: Sequence[BaseTool]) -> DedupHITLToolCallsMiddleware:
    return DedupHITLToolCallsMiddleware(agent_tools=list(tools))
