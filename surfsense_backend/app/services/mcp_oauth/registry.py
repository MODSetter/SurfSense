"""Registry of MCP services with OAuth 2.1 support.

Each entry maps a URL-safe service key to its MCP server endpoint and
authentication strategy.  Services with ``supports_dcr=True`` will use
RFC 7591 Dynamic Client Registration; the rest require pre-configured
credentials via environment variables.
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
    ),
    "airtable": MCPServiceConfig(
        name="Airtable",
        mcp_url="https://mcp.airtable.com/mcp",
        connector_type="AIRTABLE_CONNECTOR",
        oauth_discovery_origin="https://airtable.com",
        supports_dcr=False,
        client_id_env="AIRTABLE_CLIENT_ID",
        client_secret_env="AIRTABLE_CLIENT_SECRET",
    ),
}


def get_service(key: str) -> MCPServiceConfig | None:
    return MCP_SERVICES.get(key)
