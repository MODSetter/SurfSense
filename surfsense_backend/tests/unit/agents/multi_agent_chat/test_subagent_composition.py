"""Guardrail B: the subagent registry composition must stay intact.

A structural move can silently drop, rename, or mis-wire a subagent builder
(e.g. a forgotten import line). The compiled agent would then quietly lose a
specialist with no ImportError. This test pins the exact registry contents and
their cross-references so any such drift fails loudly.
"""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.constants import (
    SUBAGENT_TO_REQUIRED_CONNECTOR_MAP,
)
from app.agents.chat.multi_agent_chat.subagents.registry import (
    SUBAGENT_BUILDERS_BY_NAME,
)

pytestmark = pytest.mark.unit

# The full specialist roster the main agent composes from after the MCP
# migration: builtins + the three file-connector routes (Drive/Dropbox/
# OneDrive). Every MCP-backed connector (Slack/Jira/Linear/ClickUp/Airtable/
# Notion/Confluence/Gmail/Calendar) now lives behind the single
# ``mcp_discovery`` route; Discord/Teams/Luma were deprecated. Adding/removing a
# specialist is a deliberate product change and must be reflected here.
_EXPECTED_SUBAGENTS = frozenset(
    {
        "amazon",
        "deliverables",
        "dropbox",
        "google_drive",
        "google_maps",
        "google_search",
        "indeed",
        "instagram",
        "knowledge_base",
        "mcp_discovery",
        "memory",
        "onedrive",
        "reddit",
        "tiktok",
        "walmart",
        "web_crawler",
        "youtube",
    }
)

# Specialists that are always available regardless of connected sources, so they
# carry no required-connector entry.
_CONNECTORLESS = frozenset({"memory"})


def test_registry_contains_exactly_expected_subagents():
    """No specialist is silently added, dropped, or renamed by a move."""
    assert set(SUBAGENT_BUILDERS_BY_NAME) == _EXPECTED_SUBAGENTS


def test_every_builder_is_callable_route_agent():
    """Each registry value is a callable defined in its route's ``agent`` module."""
    for name, builder in SUBAGENT_BUILDERS_BY_NAME.items():
        assert callable(builder), f"{name} builder is not callable"
        assert builder.__module__.endswith(".agent"), (
            f"{name} builder lives in {builder.__module__}, expected a *.agent module"
        )


def test_required_connector_map_covers_connector_subagents():
    """The connector-gating map stays in lockstep with the registry."""
    assert set(SUBAGENT_TO_REQUIRED_CONNECTOR_MAP) == (
        _EXPECTED_SUBAGENTS - _CONNECTORLESS
    )
