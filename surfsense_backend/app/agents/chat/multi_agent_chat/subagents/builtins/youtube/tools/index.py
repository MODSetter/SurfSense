"""``youtube`` sub-agent tools: the YouTube scrape + comments capability verbs."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.capabilities.core.access.agent import build_capability_tools
from app.capabilities.youtube.comments.definition import YOUTUBE_COMMENTS
from app.capabilities.youtube.scrape.definition import YOUTUBE_SCRAPE

NAME = "youtube"

RULESET = Ruleset(origin=NAME, rules=[])

_CI_VERBS = [YOUTUBE_SCRAPE, YOUTUBE_COMMENTS]


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    return build_capability_tools(
        workspace_id=d.get("workspace_id"),
        capabilities=_CI_VERBS,
    )
