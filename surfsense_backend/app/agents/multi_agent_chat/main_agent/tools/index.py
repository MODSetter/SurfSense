"""Main-agent SurfSense builtin tool names (not full ``new_chat``).

Connector integrations, MCP, deliverables, etc. are delegated via ``task`` subagents.
"""

from __future__ import annotations

MAIN_AGENT_SURFSENSE_TOOL_NAMES_ORDERED: tuple[str, ...] = (
    "search_surfsense_docs",
    "web_search",
    "scrape_webpage",
    "update_memory",
)

MAIN_AGENT_SURFSENSE_TOOL_NAMES: frozenset[str] = frozenset(
    MAIN_AGENT_SURFSENSE_TOOL_NAMES_ORDERED,
)
