"""Discover MCP tools, bucket by connector agent, apply allow/ask from policy."""

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
from app.agents.multi_agent_chat.subagents.mcp_tools.permissions import (
    TOOLS_PERMISSIONS_BY_AGENT,
)
from app.agents.multi_agent_chat.subagents.shared.permissions import (
    ToolPermissionItem,
    ToolsPermissions,
    mcp_tool_permission_row,
)
from app.agents.new_chat.tools.mcp_tool import load_mcp_tools
from app.db import SearchSourceConnector

logger = logging.getLogger(__name__)


## Helper functions for fetching connector metadata maps


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


## Helper functions for partitioning tools by connector agent


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


## Helper functions for splitting tools by permissions


def _get_mcp_tool_name(tool: BaseTool) -> str:
    meta: dict[str, Any] = getattr(tool, "metadata", None) or {}
    orig = meta.get("mcp_original_tool_name")
    if isinstance(orig, str) and orig:
        return orig
    return getattr(tool, "name", "") or ""


def _split_tools_by_permissions(
    tools: Sequence[BaseTool],
    perms: ToolsPermissions,
) -> ToolsPermissions:
    allow_names = frozenset(r["name"] for r in perms["allow"])
    ask_names = frozenset(r["name"] for r in perms["ask"])
    allow: list[ToolPermissionItem] = []
    ask: list[ToolPermissionItem] = []
    for t in tools:
        meta: dict[str, Any] = getattr(t, "metadata", None) or {}
        if meta.get("hitl") is False:
            allow.append(mcp_tool_permission_row(t))
            continue
        key = _get_mcp_tool_name(t)
        if key in allow_names:
            allow.append(mcp_tool_permission_row(t))
        elif key in ask_names:
            ask.append(mcp_tool_permission_row(t))
        else:
            ask.append(mcp_tool_permission_row(t))
    return {"allow": allow, "ask": ask}


## Main function to load MCP tools and split them by permissions for each connector agent


async def load_mcp_tools_by_connector(
    session: AsyncSession,
    search_space_id: int,
) -> dict[str, ToolsPermissions]:
    """Load MCP tools and split rows using ``TOOLS_PERMISSIONS_BY_AGENT`` name sets.

    Pass ``bypass_internal_hitl=True`` so the subagent's
    ``HumanInTheLoopMiddleware`` is the single HITL gate.
    """
    flat = await load_mcp_tools(session, search_space_id, bypass_internal_hitl=True)
    id_map, name_map = await fetch_mcp_connector_metadata_maps(session, search_space_id)
    buckets = partition_mcp_tools_by_connector(flat, id_map, name_map)
    return {
        agent: _split_tools_by_permissions(
            tools,
            TOOLS_PERMISSIONS_BY_AGENT.get(agent, {"allow": [], "ask": []}),
        )
        for agent, tools in buckets.items()
    }
