"""Registry of MCP services with OAuth support.

Each entry maps a URL-safe service key to its MCP server endpoint and
authentication configuration.  Services with ``supports_dcr=True`` use
RFC 7591 Dynamic Client Registration (the MCP server issues its own
credentials); the rest use pre-configured credentials via env vars.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MCPServiceConfig:
    name: str
    mcp_url: str
    connector_type: str
    supports_dcr: bool = True
    oauth_discovery_origin: str | None = None
    client_id_env: str | None = None
    client_secret_env: str | None = None
    scopes: list[str] = field(default_factory=list)
    scope_param: str = "scope"
    auth_endpoint_override: str | None = None
    token_endpoint_override: str | None = None


MCP_SERVICES: dict[str, MCPServiceConfig] = {
    "linear": MCPServiceConfig(
        name="Linear",
        mcp_url="https://mcp.linear.app/mcp",
        connector_type="LINEAR_CONNECTOR",
    ),
    "jira": MCPServiceConfig(
        name="Jira",
        mcp_url="https://mcp.atlassian.com/v1/mcp",
        connector_type="JIRA_CONNECTOR",
    ),
    "clickup": MCPServiceConfig(
        name="ClickUp",
        mcp_url="https://mcp.clickup.com/mcp",
        connector_type="CLICKUP_CONNECTOR",
    ),
    "slack": MCPServiceConfig(
        name="Slack",
        mcp_url="https://mcp.slack.com/mcp",
        connector_type="SLACK_CONNECTOR",
        supports_dcr=False,
        client_id_env="SLACK_CLIENT_ID",
        client_secret_env="SLACK_CLIENT_SECRET",
        scope_param="user_scope",
        auth_endpoint_override="https://slack.com/oauth/v2/authorize",
        token_endpoint_override="https://slack.com/api/oauth.v2.access",
        scopes=[
            "search:read.public", "search:read.private", "search:read.mpim",
            "search:read.im", "search:read.files", "search:read.users",
            "chat:write",
            "channels:history", "groups:history", "mpim:history", "im:history",
            "canvases:read", "canvases:write",
            "users:read", "users:read.email",
        ],
    ),
    "airtable": MCPServiceConfig(
        name="Airtable",
        mcp_url="https://mcp.airtable.com/mcp",
        connector_type="AIRTABLE_CONNECTOR",
        supports_dcr=False,
        oauth_discovery_origin="https://airtable.com",
        client_id_env="AIRTABLE_CLIENT_ID",
        client_secret_env="AIRTABLE_CLIENT_SECRET",
        scopes=["data.records:read", "data.records:write", "schema.bases:read", "schema.bases:write"],
    ),
}


def get_service(key: str) -> MCPServiceConfig | None:
    return MCP_SERVICES.get(key)
