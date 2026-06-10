"""Retry on transient model errors (e.g. Retry-After-bearing 429s)."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.chat.shared.middleware import RetryAfterMiddleware

from ..flags import enabled


def build_retry_mw(flags: AgentFeatureFlags) -> RetryAfterMiddleware | None:
    return (
        RetryAfterMiddleware(max_retries=3)
        if enabled(flags, "enable_retry_after")
        else None
    )
