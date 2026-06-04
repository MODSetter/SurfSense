"""Discover MCP tools and bucket them by connector agent.

Tool gating is no longer the loader's concern: each subagent declares its
own :class:`Ruleset` and the per-subagent :class:`PermissionMiddleware`
enforces it at runtime. This module just routes flat ``BaseTool`` lists
to the right subagents.
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

from app.agents.multi_agent_chat.constants import (
    CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS,
)
from app.agents.shared.tools.mcp_tool import load_mcp_tools
from app.db import SearchSourceConnector

logger = logging.getLogger(__name__)


async def fetch_mcp_connector_metadata_maps(
    session: AsyncSession,
    search_space_id: int,
) -> tuple[dict[int, str], dict[str, str]]:
    """Resolve connector id and display name to connector type for MCP tool routing."""
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


def partition_mcp_tools_by_connector(
    tools: Sequence[BaseTool],
    connector_id_to_type: dict[int, str],
    connector_name_to_type: dict[str, str],
) -> dict[str, list[BaseTool]]:
    """Assign each MCP tool to one connector-agent bucket from connector metadata."""
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

        connector_agent = CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS.get(connector_type)
        if connector_agent is None:
            logger.warning(
                "MCP tool %r has unmapped connector type %s — skipped",
                getattr(tool, "name", None),
                connector_type,
            )
            continue

        buckets[connector_agent].append(tool)

    return dict(buckets)


async def load_mcp_tools_by_connector(
    session: AsyncSession,
    search_space_id: int,
) -> dict[str, list[BaseTool]]:
    """Load MCP tools and route them to each subagent as a flat list.

    ``bypass_internal_hitl=True`` is set so tool gating is uniformly the
    consuming subagent's :class:`PermissionMiddleware` responsibility.
    """
    flat = await load_mcp_tools(session, search_space_id, bypass_internal_hitl=True)
    id_map, name_map = await fetch_mcp_connector_metadata_maps(session, search_space_id)
    return partition_mcp_tools_by_connector(flat, id_map, name_map)
