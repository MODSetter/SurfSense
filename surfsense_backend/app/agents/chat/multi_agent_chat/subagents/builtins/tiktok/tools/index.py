"""``tiktok`` sub-agent tools: scrape, comments, user-search, and trending verbs."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.capabilities.core.access.agent import build_capability_tools
from app.capabilities.tiktok.comments.definition import TIKTOK_COMMENTS
from app.capabilities.tiktok.scrape.definition import TIKTOK_SCRAPE
from app.capabilities.tiktok.trending.definition import TIKTOK_TRENDING
from app.capabilities.tiktok.user_search.definition import TIKTOK_USER_SEARCH

NAME = "tiktok"

RULESET = Ruleset(origin=NAME, rules=[])

_CI_VERBS = [TIKTOK_SCRAPE, TIKTOK_COMMENTS, TIKTOK_USER_SEARCH, TIKTOK_TRENDING]


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    return build_capability_tools(
        workspace_id=d.get("workspace_id"),
        capabilities=_CI_VERBS,
    )
