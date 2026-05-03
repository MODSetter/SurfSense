"""Connected-accounts discovery tool.

Lets the LLM discover which accounts are connected for a given service
(e.g. "jira", "linear", "slack") and retrieve the metadata it needs to
call action tools — such as Jira's ``cloudId``.

The tool returns **only** non-sensitive fields explicitly listed in the
service's ``account_metadata_keys`` (see ``registry.py``), plus the
always-present ``display_name`` and ``connector_id``.
"""

import logging
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import SearchSourceConnector, SearchSourceConnectorType
from app.services.mcp_oauth.registry import MCP_SERVICES

logger = logging.getLogger(__name__)

_SERVICE_KEY_BY_CONNECTOR_TYPE: dict[str, str] = {
    cfg.connector_type: key for key, cfg in MCP_SERVICES.items()
}


class GetConnectedAccountsInput(BaseModel):
    service: str = Field(
        description=(
            "Service key to look up connected accounts for. "
            "Valid values: " + ", ".join(sorted(MCP_SERVICES.keys()))
        ),
    )


def _extract_display_name(connector: SearchSourceConnector) -> str:
    """Best-effort human-readable label for a connector."""
    cfg = connector.config or {}
    if cfg.get("display_name"):
        return cfg["display_name"]
    if cfg.get("base_url"):
        return f"{connector.name} ({cfg['base_url']})"
    if cfg.get("organization_name"):
        return f"{connector.name} ({cfg['organization_name']})"
    return connector.name


def create_get_connected_accounts_tool(
    db_session: AsyncSession,
    search_space_id: int,
    user_id: str,
) -> StructuredTool:

    async def _run(service: str) -> list[dict[str, Any]]:
        svc_cfg = MCP_SERVICES.get(service)
        if not svc_cfg:
            return [
                {
                    "error": f"Unknown service '{service}'. Valid: {', '.join(sorted(MCP_SERVICES.keys()))}"
                }
            ]

        try:
            connector_type = SearchSourceConnectorType(svc_cfg.connector_type)
        except ValueError:
            return [{"error": f"Connector type '{svc_cfg.connector_type}' not found."}]

        result = await db_session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == search_space_id,
                SearchSourceConnector.user_id == user_id,
                SearchSourceConnector.connector_type == connector_type,
            )
        )
        connectors = result.scalars().all()

        if not connectors:
            return [
                {
                    "error": f"No {svc_cfg.name} accounts connected. Ask the user to connect one in settings."
                }
            ]

        is_multi = len(connectors) > 1

        accounts: list[dict[str, Any]] = []
        for conn in connectors:
            cfg = conn.config or {}
            entry: dict[str, Any] = {
                "connector_id": conn.id,
                "display_name": _extract_display_name(conn),
                "service": service,
            }
            if is_multi:
                entry["tool_prefix"] = f"{service}_{conn.id}"
            for key in svc_cfg.account_metadata_keys:
                if key in cfg:
                    entry[key] = cfg[key]
            accounts.append(entry)

        return accounts

    return StructuredTool(
        name="get_connected_accounts",
        description=(
            "Discover which accounts are connected for a service (e.g. jira, linear, slack, clickup, airtable). "
            "Returns display names and service-specific metadata the action tools need "
            "(e.g. Jira's cloudId). Call this BEFORE using a service's action tools when "
            "you need an account identifier or are unsure which account to use."
        ),
        coroutine=_run,
        args_schema=GetConnectedAccountsInput,
        metadata={"hitl": False},
    )
