"""LLM-based tool subset selection (only when >30 tools)."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from langchain.agents.middleware import LLMToolSelectorMiddleware
from langchain_core.tools import BaseTool

from app.agents.new_chat.feature_flags import AgentFeatureFlags

from ..shared.flags import enabled


def build_selector_mw(
    *,
    flags: AgentFeatureFlags,
    tools: Sequence[BaseTool],
) -> LLMToolSelectorMiddleware | None:
    if not enabled(flags, "enable_llm_tool_selector") or len(tools) <= 30:
        return None
    try:
        return LLMToolSelectorMiddleware(
            model="openai:gpt-4o-mini",
            max_tools=12,
            always_include=[
                name
                for name in (
                    "update_memory",
                    "get_connected_accounts",
                    "scrape_webpage",
                )
                if name in {t.name for t in tools}
            ],
        )
    except Exception:
        logging.warning("LLMToolSelectorMiddleware init failed; skipping.")
        return None
