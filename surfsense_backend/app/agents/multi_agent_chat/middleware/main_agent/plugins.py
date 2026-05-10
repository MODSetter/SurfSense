"""Tail-of-stack plugin slot driven by env allowlist."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.plugin_loader import (
    PluginContext,
    load_allowed_plugin_names_from_env,
    load_plugin_middlewares,
)
from app.db import ChatVisibility

from ..shared.flags import enabled


def build_plugin_middlewares(
    *,
    flags: AgentFeatureFlags,
    search_space_id: int,
    user_id: str | None,
    visibility: ChatVisibility,
    llm: BaseChatModel,
) -> list[Any]:
    if not enabled(flags, "enable_plugin_loader"):
        return []
    try:
        allowed_names = load_allowed_plugin_names_from_env()
        if not allowed_names:
            return []
        return load_plugin_middlewares(
            PluginContext.build(
                search_space_id=search_space_id,
                user_id=user_id,
                thread_visibility=visibility,
                llm=llm,
            ),
            allowed_plugin_names=allowed_names,
        )
    except Exception:  # pragma: no cover - defensive
        logging.warning(
            "Plugin loader failed; continuing without plugins.",
            exc_info=True,
        )
        return []
