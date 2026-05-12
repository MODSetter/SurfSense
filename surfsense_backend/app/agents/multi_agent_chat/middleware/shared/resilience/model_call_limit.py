"""Cap model calls per thread / per run to prevent runaway cost."""

from __future__ import annotations

from langchain.agents.middleware import ModelCallLimitMiddleware

from app.agents.new_chat.feature_flags import AgentFeatureFlags

from ..flags import enabled


def build_model_call_limit_mw(
    flags: AgentFeatureFlags,
) -> ModelCallLimitMiddleware | None:
    if not enabled(flags, "enable_model_call_limit"):
        return None
    return ModelCallLimitMiddleware(
        thread_limit=120,
        run_limit=80,
        exit_behavior="end",
    )
