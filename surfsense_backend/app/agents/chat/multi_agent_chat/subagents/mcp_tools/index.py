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

from app.agents.chat.multi_agent_chat.constants import (
    CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import load_mcp_tools
from app.db import SearchSourceConnector
from app.services.mcp_oauth.registry import MCP_SERVICES, get_service_by_connector_type

logger = logging.getLogger(__name__)


def _service_key_for_type(connector_type: str | None) -> str | None:
    """Return the ``MCP_SERVICES`` key for a connector type, if any."""
    if connector_type is None:
        return None
    svc = get_service_by_connector_type(connector_type)
    if svc is None:
        return None
    return next((k for k, v in MCP_SERVICES.items() if v is svc), None)


def resolve_tool_name_collisions(
    tools: Sequence[BaseTool],
    connector_id_to_type: dict[int, str],
) -> list[BaseTool]:
    """Prefix only the tools whose exposed name collides across connectors.

    All MCP tools now merge into a single ``mcp_discovery`` subagent, so two
    apps advertising the same tool name (e.g. Jira and Confluence both expose
    ``getAccessibleAtlassianResources``) would otherwise shadow each other.
    We detect names carried by more than one distinct connector and rebuild
    just those with a ``{service_key_or_mcp}_{connector_id}_`` prefix — the
    same convention as the existing multi-account prefixing. Non-colliding
    tools keep their names, so stored ``trusted_tools`` and HITL history stay
    valid in the common case; for the prefixed ones,
    ``metadata['mcp_original_tool_name']`` is preserved as the "Always Allow"
    fallback key.
    """
    names_to_connectors: dict[str, set[int]] = defaultdict(set)
    for tool in tools:
        meta = getattr(tool, "metadata", None) or {}
        cid = meta.get("mcp_connector_id")
        if isinstance(cid, int):
            names_to_connectors[tool.name].add(cid)

    colliding = {n for n, cids in names_to_connectors.items() if len(cids) > 1}
    if not colliding:
        return list(tools)

    resolved: list[BaseTool] = []
    for tool in tools:
        meta = getattr(tool, "metadata", None) or {}
        cid = meta.get("mcp_connector_id")
        if tool.name not in colliding or not isinstance(cid, int):
            resolved.append(tool)
            continue

        original_name = tool.name
        prefix = _service_key_for_type(connector_id_to_type.get(cid)) or "mcp"
        new_name = f"{prefix}_{cid}_{original_name}"
        new_meta = {
            **meta,
            "mcp_original_tool_name": meta.get("mcp_original_tool_name")
            or original_name,
            "mcp_collision_prefixed": True,
        }
        resolved.append(tool.model_copy(update={"name": new_name, "metadata": new_meta}))
    return resolved


async def fetch_mcp_connector_metadata_maps(
    session: AsyncSession,
    workspace_id: int,
) -> tuple[dict[int, str], dict[str, str]]:
    """Resolve connector id and display name to connector type for MCP tool routing."""
    result = await session.execute(
        select(SearchSourceConnector).filter(
            SearchSourceConnector.workspace_id == workspace_id,
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
    workspace_id: int,
) -> dict[str, list[BaseTool]]:
    """Load MCP tools and route them to each subagent as a flat list.

    ``bypass_internal_hitl=True`` is set so tool gating is uniformly the
    consuming subagent's :class:`PermissionMiddleware` responsibility.
    """
    flat = await load_mcp_tools(session, workspace_id, bypass_internal_hitl=True)
    id_map, name_map = await fetch_mcp_connector_metadata_maps(session, workspace_id)
    flat = resolve_tool_name_collisions(flat, id_map)
    return partition_mcp_tools_by_connector(flat, id_map, name_map)
