from __future__ import annotations

from typing import Any

from app.agents.multi_agent_chat.subagents.shared.hitl.approvals.self_gated import (
    self_gated_tool_permission_row,
)
from app.agents.multi_agent_chat.subagents.shared.tool_kinds import (
    ToolsPermissions,
)

from .scrape_webpage import create_scrape_webpage_tool
from .search_surfsense_docs import create_search_surfsense_docs_tool
from .web_search import create_web_search_tool


def load_tools(
    *, dependencies: dict[str, Any] | None = None, **kwargs: Any
) -> ToolsPermissions:
    resolved_dependencies = {**(dependencies or {}), **kwargs}
    web = create_web_search_tool(
        search_space_id=resolved_dependencies.get("search_space_id"),
        available_connectors=resolved_dependencies.get("available_connectors"),
    )
    scrape = create_scrape_webpage_tool(
        firecrawl_api_key=resolved_dependencies.get("firecrawl_api_key")
    )
    docs = create_search_surfsense_docs_tool(
        db_session=resolved_dependencies["db_session"]
    )
    return {
        "allow": [
            self_gated_tool_permission_row(web),
            self_gated_tool_permission_row(scrape),
            self_gated_tool_permission_row(docs),
        ],
        "ask": [],
    }
