"""``research`` native tools and (empty) permission ruleset."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.new_chat.permissions import Ruleset

from .scrape_webpage import create_scrape_webpage_tool
from .web_search import create_web_search_tool

NAME = "research"

RULESET = Ruleset(origin=NAME, rules=[])


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> list[BaseTool]:
    d = {**(dependencies or {}), **kwargs}
    return [
        create_web_search_tool(
            search_space_id=d.get("search_space_id"),
            available_connectors=d.get("available_connectors"),
        ),
        create_scrape_webpage_tool(firecrawl_api_key=d.get("firecrawl_api_key")),
    ]
