"""Per-thread cooperative lock around the whole turn."""

from __future__ import annotations

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.middleware import BusyMutexMiddleware

from ..shared.flags import enabled


def build_busy_mutex_mw(flags: AgentFeatureFlags) -> BusyMutexMiddleware | None:
    return BusyMutexMiddleware() if enabled(flags, "enable_busy_mutex") else None
