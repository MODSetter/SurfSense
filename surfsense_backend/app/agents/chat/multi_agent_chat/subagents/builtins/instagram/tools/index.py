"""``instagram`` sub-agent tools: the three Instagram capability verbs."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.capabilities.core.access.agent import build_capability_tools
from app.capabilities.instagram.comments.definition import INSTAGRAM_COMMENTS
from app.capabilities.instagram.details.definition import INSTAGRAM_DETAILS
from app.capabilities.instagram.scrape.definition import INSTAGRAM_SCRAPE

NAME = "instagram"

RULESET = Ruleset(origin=NAME, rules=[])

_CI_VERBS = [INSTAGRAM_SCRAPE, INSTAGRAM_COMMENTS, INSTAGRAM_DETAILS]


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    return build_capability_tools(
        workspace_id=d.get("workspace_id"),
        capabilities=_CI_VERBS,
    )
