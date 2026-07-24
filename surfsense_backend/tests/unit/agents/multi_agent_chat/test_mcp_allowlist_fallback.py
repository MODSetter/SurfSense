"""Allowlist filtering in ``_load_http_mcp_tools``.

Covers the fallback added after Notion renamed its MCP tools ("notion-"
prefix) and a stale allowlist silently disabled the connector: when the
allowlist matches zero advertised tools, load everything (HITL-gated)
instead of nothing.
"""

from datetime import UTC, datetime

from app.agents.chat.multi_agent_chat.shared.tools.mcp.cache import (
    CachedMCPTools,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
    _load_http_mcp_tools,
)

_CACHED = CachedMCPTools(
    discovered_at=datetime.now(UTC),
    tools=[
        {"name": "notion-search", "description": "search", "input_schema": {}},
        {"name": "notion-update-page", "description": "write", "input_schema": {}},
    ],
)
_SERVER_CONFIG = {"url": "https://example.com/mcp", "headers": {}}


async def test_allowlist_match_filters_and_flags_readonly():
    tools = await _load_http_mcp_tools(
        1,
        "Notion",
        _SERVER_CONFIG,
        allowed_tools=["notion-search"],
        readonly_tools=frozenset({"notion-search"}),
        cached_tools=_CACHED,
    )
    assert [t.name for t in tools] == ["notion-search"]
    assert tools[0].metadata["hitl"] is False


async def test_stale_allowlist_falls_back_to_all_tools_hitl_gated():
    tools = await _load_http_mcp_tools(
        1,
        "Notion",
        _SERVER_CONFIG,
        allowed_tools=["search", "update-page"],  # server renamed everything
        readonly_tools=frozenset({"search"}),
        cached_tools=_CACHED,
    )
    assert sorted(t.name for t in tools) == ["notion-search", "notion-update-page"]
    # Renamed tools match no readonly entry -> every tool requires approval.
    assert all(t.metadata["hitl"] is True for t in tools)
