"""Per-thread cooperative lock around the whole turn."""

from __future__ import annotations

from app.agents.shared.feature_flags import AgentFeatureFlags
from app.agents.shared.middleware import BusyMutexMiddleware

from app.agents.multi_agent_chat.middleware.shared.flags import enabled


def build_busy_mutex_mw(flags: AgentFeatureFlags) -> BusyMutexMiddleware | None:
    return BusyMutexMiddleware() if enabled(flags, "enable_busy_mutex") else None
