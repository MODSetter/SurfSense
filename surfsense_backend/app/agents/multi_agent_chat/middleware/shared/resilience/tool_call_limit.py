"""Cap tool calls per thread / per run to bound infinite-loop blast radius."""

from __future__ import annotations

from langchain.agents.middleware import ToolCallLimitMiddleware

from app.agents.new_chat.feature_flags import AgentFeatureFlags

from ..flags import enabled


def build_tool_call_limit_mw(
    flags: AgentFeatureFlags,
) -> ToolCallLimitMiddleware | None:
    if not enabled(flags, "enable_tool_call_limit"):
        return None
    return ToolCallLimitMiddleware(
        thread_limit=300,
        run_limit=80,
        exit_behavior="continue",
    )
