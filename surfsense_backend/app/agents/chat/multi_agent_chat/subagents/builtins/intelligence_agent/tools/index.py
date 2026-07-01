"""``intelligence_agent`` tools: web.* verbs generated from the capability registry."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.capabilities.access.agent import build_capability_tools
from app.capabilities.web.discover.definition import WEB_DISCOVER
from app.capabilities.web.scrape.definition import WEB_SCRAPE

NAME = "intelligence_agent"

RULESET = Ruleset(origin=NAME, rules=[])

_CI_VERBS = [WEB_DISCOVER, WEB_SCRAPE]


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    return build_capability_tools(
        workspace_id=d.get("workspace_id"),
        capabilities=_CI_VERBS,
    )
