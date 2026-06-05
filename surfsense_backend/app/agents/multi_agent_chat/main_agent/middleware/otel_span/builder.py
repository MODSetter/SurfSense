"""OTel spans on model and tool calls."""

from __future__ import annotations

from app.agents.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.multi_agent_chat.shared.middleware.flags import enabled

from .middleware import OtelSpanMiddleware


def build_otel_mw(flags: AgentFeatureFlags) -> OtelSpanMiddleware | None:
    return OtelSpanMiddleware() if enabled(flags, "enable_otel") else None
