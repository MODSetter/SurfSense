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
    supports_dcr: bool = True
    client_id_env: str | None = None
    client_secret_env: str | None = None
    scopes: list[str] = field(default_factory=list)


MCP_SERVICES: dict[str, MCPServiceConfig] = {
    "linear": MCPServiceConfig(
        name="Linear",
        mcp_url="https://mcp.linear.app/mcp",
    ),
    "jira": MCPServiceConfig(
        name="Jira",
        mcp_url="https://mcp.atlassian.com/v1/mcp",
    ),
    "clickup": MCPServiceConfig(
        name="ClickUp",
        mcp_url="https://mcp.clickup.com/mcp",
    ),
}


def get_service(key: str) -> MCPServiceConfig | None:
    return MCP_SERVICES.get(key)
