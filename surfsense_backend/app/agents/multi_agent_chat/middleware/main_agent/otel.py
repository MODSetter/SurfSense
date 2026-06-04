"""OTel spans on model and tool calls."""

from __future__ import annotations

from app.agents.shared.feature_flags import AgentFeatureFlags
from app.agents.shared.middleware import OtelSpanMiddleware

from ..shared.flags import enabled


def build_otel_mw(flags: AgentFeatureFlags) -> OtelSpanMiddleware | None:
    return OtelSpanMiddleware() if enabled(flags, "enable_otel") else None
