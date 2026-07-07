"""``reddit`` sub-agent tools: the Reddit scrape capability verb."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.capabilities.core.access.agent import build_capability_tools
from app.capabilities.reddit.scrape.definition import REDDIT_SCRAPE

NAME = "reddit"

RULESET = Ruleset(origin=NAME, rules=[])

_CI_VERBS = [REDDIT_SCRAPE]


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    return build_capability_tools(
        workspace_id=d.get("workspace_id"),
        capabilities=_CI_VERBS,
    )
