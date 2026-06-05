"""Per-thread cooperative lock around the whole turn."""

from __future__ import annotations

from app.agents.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.multi_agent_chat.shared.middleware.busy_mutex import BusyMutexMiddleware
from app.agents.multi_agent_chat.shared.middleware.flags import enabled


def build_busy_mutex_mw(flags: AgentFeatureFlags) -> BusyMutexMiddleware | None:
    return BusyMutexMiddleware() if enabled(flags, "enable_busy_mutex") else None
