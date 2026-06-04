"""Unit tests for ``mcp_tools_cache``."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.agents.shared.tools.mcp_tools_cache import (
    CachedMCPToolDef,
    CachedMCPTools,
    read_cached_tools,
)

pytestmark = pytest.mark.unit


def _make_connector(config: dict | None) -> SimpleNamespace:
    return SimpleNamespace(id=42, config=config)


def test_read_returns_none_when_config_is_none() -> None:
    assert read_cached_tools(_make_connector(None)) is None


def test_read_returns_none_when_cached_tools_missing() -> None:
    assert read_cached_tools(_make_connector({"server_config": {}})) is None


def test_read_returns_none_when_cached_tools_is_not_a_dict() -> None:
    assert read_cached_tools(_make_connector({"cached_tools": []})) is None
    assert read_cached_tools(_make_connector({"cached_tools": "stale"})) is None


def test_read_parses_minimal_valid_payload() -> None:
    parsed = read_cached_tools(
        _make_connector(
            {
                "cached_tools": {
                    "discovered_at": "2026-05-20T10:00:00+00:00",
                    "tools": [
                        {
                            "name": "list_issues",
                            "description": "List Linear issues",
                            "input_schema": {"type": "object"},
                        }
                    ],
                }
            }
        )
    )
    assert parsed is not None
    assert parsed.server_version is None
    assert parsed.server_name is None
    assert parsed.transport is None
    assert len(parsed.tools) == 1
    assert parsed.tools[0].name == "list_issues"


def test_read_parses_full_payload_with_serverinfo() -> None:
    parsed = read_cached_tools(
        _make_connector(
            {
                "cached_tools": {
                    "discovered_at": "2026-05-20T10:00:00+00:00",
                    "server_version": "1.2.3",
                    "server_name": "atlassian-mcp",
                    "transport": "streamable-http",
                    "tools": [
                        {"name": "create_issue", "input_schema": {}},
                        {"name": "list_issues", "input_schema": {}},
                    ],
                }
            }
        )
    )
    assert parsed is not None
    assert parsed.server_version == "1.2.3"
    assert parsed.server_name == "atlassian-mcp"
    assert parsed.transport == "streamable-http"
    assert [t.name for t in parsed.tools] == ["create_issue", "list_issues"]


def test_read_returns_none_for_corrupt_payload(caplog) -> None:
    parsed = read_cached_tools(
        _make_connector(
            {
                "cached_tools": {
                    "discovered_at": "not-a-date",
                    "tools": "should-be-a-list",
                }
            }
        )
    )
    assert parsed is None
    assert any("corrupt cached_tools" in r.getMessage() for r in caplog.records)


def test_read_returns_none_when_tools_missing() -> None:
    parsed = read_cached_tools(
        _make_connector(
            {"cached_tools": {"discovered_at": "2026-05-20T10:00:00+00:00"}}
        )
    )
    assert parsed is None


def test_tool_def_defaults_description_and_schema() -> None:
    td = CachedMCPToolDef.model_validate({"name": "ping"})
    assert td.description == ""
    assert td.input_schema == {}


def test_model_dump_json_mode_is_round_trippable() -> None:
    original = CachedMCPTools(
        discovered_at=datetime(2026, 5, 20, 10, 0, 0, tzinfo=UTC),
        server_version="1.2.3",
        server_name="atlassian-mcp",
        transport="streamable-http",
        tools=[CachedMCPToolDef(name="list_issues")],
    )
    payload = original.model_dump(mode="json")

    assert payload["discovered_at"] == "2026-05-20T10:00:00Z"
    assert payload["tools"][0]["name"] == "list_issues"

    reparsed = CachedMCPTools.model_validate(payload)
    assert reparsed.discovered_at == original.discovered_at
    assert reparsed.tools[0].name == "list_issues"
