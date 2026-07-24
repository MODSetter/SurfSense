"""``google_maps`` sub-agent tools: the Google Maps scrape + reviews capability verbs."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.shared.permissions import Ruleset
from app.capabilities.core.access.agent import build_capability_tools
from app.capabilities.google_maps.reviews.definition import GOOGLE_MAPS_REVIEWS
from app.capabilities.google_maps.scrape.definition import GOOGLE_MAPS_SCRAPE

NAME = "google_maps"

RULESET = Ruleset(origin=NAME, rules=[])

_CI_VERBS = [GOOGLE_MAPS_SCRAPE, GOOGLE_MAPS_REVIEWS]


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    return build_capability_tools(
        workspace_id=d.get("workspace_id"),
        capabilities=_CI_VERBS,
    )
