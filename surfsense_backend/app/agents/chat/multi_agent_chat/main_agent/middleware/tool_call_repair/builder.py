"""Repair miscased / unknown tool names to the registered set or invalid_tool."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.chat.multi_agent_chat.shared.middleware.flags import enabled

from .middleware import ToolCallNameRepairMiddleware

_MIDDLEWARE_BOUND_TOOL_NAMES: frozenset[str] = frozenset({"task", "write_todos"})


def build_repair_mw(
    *,
    flags: AgentFeatureFlags,
    tools: Sequence[BaseTool],
) -> ToolCallNameRepairMiddleware | None:
    if not enabled(flags, "enable_tool_call_repair"):
        return None
    registered_names: set[str] = {t.name for t in tools}
    registered_names |= _MIDDLEWARE_BOUND_TOOL_NAMES
    return ToolCallNameRepairMiddleware(
        registered_tool_names=registered_names,
        fuzzy_match_threshold=None,
    )
