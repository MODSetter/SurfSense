"""Audit row per tool call (reversibility metadata)."""

from __future__ import annotations

import logging

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.middleware import ActionLogMiddleware
from app.agents.new_chat.tools.registry import BUILTIN_TOOLS

from ..shared.flags import enabled


def build_action_log_mw(
    *,
    flags: AgentFeatureFlags,
    thread_id: int | None,
    search_space_id: int,
    user_id: str | None,
) -> ActionLogMiddleware | None:
    if not enabled(flags, "enable_action_log") or thread_id is None:
        return None
    try:
        tool_defs_by_name = {td.name: td for td in BUILTIN_TOOLS}
        return ActionLogMiddleware(
            thread_id=thread_id,
            search_space_id=search_space_id,
            user_id=user_id,
            tool_definitions=tool_defs_by_name,
        )
    except Exception:  # pragma: no cover - defensive
        logging.warning(
            "ActionLogMiddleware init failed; running without it.",
            exc_info=True,
        )
        return None
