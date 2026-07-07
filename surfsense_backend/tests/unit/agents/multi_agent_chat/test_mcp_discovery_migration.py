"""Guardrails for the MCP-consolidation migration.

Every MCP-backed connector now routes to the single ``mcp_discovery`` subagent
(file connectors stay native; Discord/Teams/Luma are deprecated). These tests
pin the pieces that make that safe: connector→route mapping, any-of gating,
legacy checkpoint aliasing, tool-name collision prefixing, the metadata-derived
approval ruleset, and the KB indexing-deprecation sets.
"""

from __future__ import annotations

import pytest
from langchain_core.tools import StructuredTool

from app.agents.chat.multi_agent_chat.constants import (
    CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS,
    LEGACY_SUBAGENT_ALIASES,
    SUBAGENT_TO_REQUIRED_CONNECTOR_MAP,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.mcp_discovery.tools.index import (
    NAME as MCP_DISCOVERY_NAME,
    build_ruleset,
)
from app.agents.chat.multi_agent_chat.subagents.mcp_tools.index import (
    resolve_tool_name_collisions,
)
from app.agents.chat.multi_agent_chat.subagents.registry import (
    SUBAGENT_BUILDERS_BY_NAME,
    get_subagents_to_exclude,
)
from app.services.mcp_oauth.registry import (
    DEPRECATED_INDEXING_CONNECTOR_TYPES,
    LIVE_CONNECTOR_TYPES,
)

pytestmark = pytest.mark.unit

# Connectors that must all funnel into ``mcp_discovery`` (not their own routes).
_MCP_ROUTED = {
    "SLACK_CONNECTOR",
    "JIRA_CONNECTOR",
    "LINEAR_CONNECTOR",
    "CLICKUP_CONNECTOR",
    "AIRTABLE_CONNECTOR",
    "NOTION_CONNECTOR",
    "CONFLUENCE_CONNECTOR",
    "GOOGLE_GMAIL_CONNECTOR",
    "GOOGLE_CALENDAR_CONNECTOR",
    "MCP_CONNECTOR",
}


def _tool(name: str, metadata: dict) -> StructuredTool:
    return StructuredTool.from_function(
        func=lambda: name,
        name=name,
        description=name,
        metadata=metadata,
    )


def test_all_mcp_connectors_route_to_discovery():
    for connector_type in _MCP_ROUTED:
        assert (
            CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS[connector_type] == MCP_DISCOVERY_NAME
        ), connector_type


def test_file_connectors_keep_native_routes():
    assert (
        CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS["GOOGLE_DRIVE_CONNECTOR"]
        == "google_drive"
    )
    assert CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS["DROPBOX_CONNECTOR"] == "dropbox"
    assert CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS["ONEDRIVE_CONNECTOR"] == "onedrive"


def test_deprecated_connectors_have_no_route():
    for connector_type in ("DISCORD_CONNECTOR", "TEAMS_CONNECTOR", "LUMA_CONNECTOR"):
        assert connector_type not in CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS


def test_discovery_gating_is_any_of():
    """One connected app is enough to keep ``mcp_discovery``; none excludes it."""
    assert MCP_DISCOVERY_NAME not in get_subagents_to_exclude(["SLACK_CONNECTOR"])
    assert MCP_DISCOVERY_NAME in get_subagents_to_exclude([])
    # A generic user MCP server alone still unlocks it.
    assert MCP_DISCOVERY_NAME not in get_subagents_to_exclude(["MCP_CONNECTOR"])


def test_discovery_gating_tokens_match_routed_connectors():
    assert SUBAGENT_TO_REQUIRED_CONNECTOR_MAP[MCP_DISCOVERY_NAME] == frozenset(
        _MCP_ROUTED
    )


def test_legacy_aliases_resolve_to_a_live_subagent():
    """Old per-connector task names must alias onto a subagent that still exists."""
    for legacy, target in LEGACY_SUBAGENT_ALIASES.items():
        assert legacy not in SUBAGENT_BUILDERS_BY_NAME, legacy
        assert target in SUBAGENT_BUILDERS_BY_NAME, target


def test_collision_only_prefixes_shared_names():
    """A name on two connectors is prefixed; a unique name is left untouched."""
    tools = [
        _tool("search", {"mcp_connector_id": 1, "mcp_transport": "http"}),
        _tool("search", {"mcp_connector_id": 2, "mcp_transport": "http"}),
        _tool("list_bases", {"mcp_connector_id": 2, "mcp_transport": "http"}),
    ]
    resolved = {
        t.name: t
        for t in resolve_tool_name_collisions(
            tools, {1: "NOTION_CONNECTOR", 2: "AIRTABLE_CONNECTOR"}
        )
    }

    # The unique tool keeps its bare name (trusted_tools / history stay valid).
    assert "list_bases" in resolved
    # The colliding name is gone; both are prefixed with service + connector id.
    assert "search" not in resolved
    assert "notion_1_search" in resolved
    assert "airtable_2_search" in resolved
    # Original name preserved for the "Always Allow" fallback key.
    for name in ("notion_1_search", "airtable_2_search"):
        meta = resolved[name].metadata or {}
        assert meta["mcp_original_tool_name"] == "search"
        assert meta["mcp_collision_prefixed"] is True


def test_collision_noop_without_collisions():
    tools = [
        _tool("a", {"mcp_connector_id": 1}),
        _tool("b", {"mcp_connector_id": 2}),
    ]
    assert [t.name for t in resolve_tool_name_collisions(tools, {})] == ["a", "b"]


def test_ruleset_reads_hitl_from_metadata():
    """Read-only MCP tools ``allow``; every other MCP tool ``ask``; natives skip."""
    tools = [
        _tool("readonly_search", {"mcp_transport": "http", "hitl": False}),
        _tool("mutating_create", {"mcp_transport": "http", "hitl": True}),
        _tool("native_helper", {}),  # no mcp_transport => no rule
    ]
    rules = {r.permission: r.action for r in build_ruleset(tools).rules}
    assert rules == {"readonly_search": "allow", "mutating_create": "ask"}


def test_indexing_deprecation_sets():
    """Indexing-only connectors are deprecated; migrated ones are LIVE; Obsidian stays."""
    deprecated = {t.value for t in DEPRECATED_INDEXING_CONNECTOR_TYPES}
    assert deprecated == {
        "GITHUB_CONNECTOR",
        "BOOKSTACK_CONNECTOR",
        "ELASTICSEARCH_CONNECTOR",
        "CIRCLEBACK_CONNECTOR",
    }
    assert "OBSIDIAN_CONNECTOR" not in deprecated

    live = {t.value for t in LIVE_CONNECTOR_TYPES}
    assert {"NOTION_CONNECTOR", "CONFLUENCE_CONNECTOR"} <= live
