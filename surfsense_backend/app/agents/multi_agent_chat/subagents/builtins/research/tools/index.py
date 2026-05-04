from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolsPermissions,
)

from .scrape_webpage import create_scrape_webpage_tool
from .search_surfsense_docs import create_search_surfsense_docs_tool
from .web_search import create_web_search_tool


def load_tools(*, dependencies: dict[str, Any] | None = None, **kwargs: Any) -> ToolsPermissions:
    resolved_dependencies = {**(dependencies or {}), **kwargs}
    web = create_web_search_tool(
        search_space_id=resolved_dependencies.get("search_space_id"),
        available_connectors=resolved_dependencies.get("available_connectors"),
    )
    scrape = create_scrape_webpage_tool(firecrawl_api_key=resolved_dependencies.get("firecrawl_api_key"))
    docs = create_search_surfsense_docs_tool(db_session=resolved_dependencies["db_session"])
    return {
        "allow": [
            {"name": getattr(web, "name", "") or "", "tool": web},
            {"name": getattr(scrape, "name", "") or "", "tool": scrape},
            {"name": getattr(docs, "name", "") or "", "tool": docs},
        ],
        "ask": [],
    }
