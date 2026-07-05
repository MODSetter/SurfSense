"""``get_connected_accounts`` — list the workspace's MCP-capable connectors.

Read-only helper the connected-apps subagent calls to discover which apps
are connected and to disambiguate multi-account / multi-site scenarios. Only
the whitelisted ``MCPServiceConfig.account_metadata_keys`` (plus
``display_name``) are exposed to the LLM — tokens, secrets, and raw
``server_config`` are never returned.
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import BaseTool, StructuredTool
from sqlalchemy import select

from app.services.mcp_oauth.registry import get_service_by_connector_type

logger = logging.getLogger(__name__)

_GENERIC_MCP_CONNECTOR_TYPE = "MCP_CONNECTOR"

_TOOL_DESCRIPTION = (
    "List the user's connected apps (Slack, Jira, Confluence, Linear, "
    "ClickUp, Airtable, Notion, Gmail, Google Calendar, and generic MCP "
    "servers) with their account/workspace/site metadata. Use this to find "
    "out which apps are connected and to pick the right account, workspace, "
    "or site before acting when more than one could match. Read-only."
)


def _connector_type_value(connector_type: object) -> str:
    return (
        connector_type.value
        if hasattr(connector_type, "value")
        else str(connector_type)
    )


def create_get_connected_accounts_tool(*, workspace_id: int) -> BaseTool:
    """Factory for the read-only ``get_connected_accounts`` tool."""
    _workspace_id = workspace_id

    async def _impl() -> str:
        # Open a fresh session inside the closure: the factory-time session may
        # be closed by the time the LLM calls this tool.
        from app.db import SearchSourceConnector, async_session_maker

        accounts: list[dict[str, object]] = []
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(SearchSourceConnector).where(
                        SearchSourceConnector.workspace_id == _workspace_id,
                    )
                )
                connectors = list(result.scalars())
        except Exception:
            logger.exception("get_connected_accounts: connector query failed")
            return json.dumps({"accounts": [], "error": "query_failed"})

        for connector in connectors:
            ct = _connector_type_value(connector.connector_type)
            svc = get_service_by_connector_type(ct)
            is_generic = ct == _GENERIC_MCP_CONNECTOR_TYPE
            if svc is None and not is_generic:
                continue  # not an MCP-capable / connected-app connector

            cfg = connector.config if isinstance(connector.config, dict) else {}
            metadata_keys = list(svc.account_metadata_keys) if svc else []
            account_meta: dict[str, object] = {
                key: cfg[key] for key in metadata_keys if cfg.get(key) is not None
            }
            display_name = cfg.get("display_name")
            if display_name and "display_name" not in account_meta:
                account_meta["display_name"] = display_name

            accounts.append(
                {
                    "connector_id": connector.id,
                    "name": connector.name,
                    "connector_type": ct,
                    "app": svc.name if svc else "Custom MCP server",
                    # ``server_config`` presence == the connector produces agent
                    # tools. Native rows without it are connected for indexing
                    # only and need a reconnect via MCP.
                    "usable_in_chat": isinstance(cfg, dict)
                    and "server_config" in cfg,
                    "account": account_meta,
                }
            )

        return json.dumps({"accounts": accounts})

    return StructuredTool.from_function(
        name="get_connected_accounts",
        description=_TOOL_DESCRIPTION,
        coroutine=_impl,
    )
