"""Audit row per tool call (reversibility metadata)."""

from __future__ import annotations

import logging

from app.agents.shared.feature_flags import AgentFeatureFlags
from app.agents.shared.middleware import ActionLogMiddleware

from app.agents.multi_agent_chat.shared.middleware.flags import enabled


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
        # No built-in tool declares a ``reverse`` callable yet, so the action
        # log runs without a tool_definitions map. Reversibility is opt-in per
        # tool via ``ToolDefinition.reverse`` and can be wired here when used.
        return ActionLogMiddleware(
            thread_id=thread_id,
            search_space_id=search_space_id,
            user_id=user_id,
        )
    except Exception:  # pragma: no cover - defensive
        logging.warning(
            "ActionLogMiddleware init failed; running without it.",
            exc_info=True,
        )
        return None
