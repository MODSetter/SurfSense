"""Partition MCP tools onto multi-agent expert routes (read-only; does not change the MCP loader).

Uses the same connector discovery shape as ``load_mcp_tools`` (copied query below). Tools come from
``app.agents.new_chat.tools.mcp_tool.load_mcp_tools``; routing uses metadata already set there:

- HTTP tools: ``metadata["mcp_connector_id"]`` → DB connector row → expert route.
- stdio tools: no connector id on the tool; ``metadata["mcp_connector_name"]`` → connector name map
  (duplicate names: last row wins — rare).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from langchain_core.tools import BaseTool
from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSourceConnector

logger = logging.getLogger(__name__)

# SurfSense ``SearchSourceConnectorType`` string → supervisor routing key (must match
# ``DomainRoutingSpec.tool_name`` values used in ``supervisor_routing``).
_CONNECTOR_TYPE_TO_EXPERT_ROUTE: dict[str, str] = {
    "GOOGLE_GMAIL_CONNECTOR": "gmail",
    "COMPOSIO_GMAIL_CONNECTOR": "gmail",
    "GOOGLE_CALENDAR_CONNECTOR": "calendar",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR": "calendar",
    "DISCORD_CONNECTOR": "discord",
    "TEAMS_CONNECTOR": "teams",
    "LUMA_CONNECTOR": "luma",
    "LINEAR_CONNECTOR": "linear",
    "JIRA_CONNECTOR": "jira",
    "CLICKUP_CONNECTOR": "clickup",
    "SLACK_CONNECTOR": "slack",
    "AIRTABLE_CONNECTOR": "airtable",
    # generic_mcp route intentionally disabled for now.
    # "MCP_CONNECTOR": "generic_mcp",
}

# Ordering when appending MCP-only routes (no native registry slice for these types).
MCP_ONLY_ROUTE_KEYS_IN_ORDER: tuple[str, ...] = (
    "linear",
    "slack",
    "jira",
    "clickup",
    "airtable",
    # generic_mcp intentionally disabled for now.
    # "generic_mcp",
)


async def fetch_mcp_connector_metadata_maps(
    session: AsyncSession,
    search_space_id: int,
) -> tuple[dict[int, str], dict[str, str]]:
    """Read-only copy of connector discovery used alongside ``load_mcp_tools``.

    Same filter as :func:`app.agents.new_chat.tools.mcp_tool.load_mcp_tools` (connectors with ``server_config``).
    """
    result = await session.execute(
        select(SearchSourceConnector).filter(
            SearchSourceConnector.search_space_id == search_space_id,
            cast(SearchSourceConnector.config, JSONB).has_key("server_config"),
        ),
    )
    id_to_type: dict[int, str] = {}
    name_to_type: dict[str, str] = {}
    for connector in result.scalars():
        ct = (
            connector.connector_type.value
            if hasattr(connector.connector_type, "value")
            else str(connector.connector_type)
        )
        id_to_type[connector.id] = ct
        if connector.name:
            name_to_type[connector.name] = ct
    return id_to_type, name_to_type


def partition_mcp_tools_by_expert_route(
    tools: Sequence[BaseTool],
    connector_id_to_type: dict[int, str],
    connector_name_to_type: dict[str, str],
) -> dict[str, list[BaseTool]]:
    """Bucket MCP tools by expert route key. Supervisor never receives raw MCP tools.

    Same inclusion rule as :func:`app.agents.new_chat.tools.registry.build_tools_async`: all tools returned by
    ``load_mcp_tools`` are partitioned — connector availability for **registry** builtins is handled via
    ``get_connector_gated_tools`` / routing gates; MCP tools are not pre-filtered by inventory here.
    """
    buckets: dict[str, list[BaseTool]] = defaultdict(list)

    for tool in tools:
        meta: dict[str, Any] = getattr(tool, "metadata", None) or {}
        connector_type: str | None = None

        cid = meta.get("mcp_connector_id")
        if cid is not None:
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                cid_int = None
            if cid_int is not None:
                connector_type = connector_id_to_type.get(cid_int)

        if connector_type is None and meta.get("mcp_transport") == "stdio":
            cname = meta.get("mcp_connector_name")
            if cname:
                connector_type = connector_name_to_type.get(str(cname))

        if connector_type is None:
            logger.debug(
                "Skipping MCP tool %r — could not resolve connector type from metadata",
                getattr(tool, "name", None),
            )
            continue

        route = _CONNECTOR_TYPE_TO_EXPERT_ROUTE.get(connector_type)
        if route is None:
            logger.warning(
                "MCP tool %r has unmapped connector type %s — skipped",
                getattr(tool, "name", None),
                connector_type,
            )
            continue

        buckets[route].append(tool)

    return dict(buckets)
