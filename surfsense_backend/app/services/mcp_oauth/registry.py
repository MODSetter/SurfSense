"""Registry of MCP services with OAuth support.

Each entry maps a URL-safe service key to its MCP server endpoint and
authentication configuration.  Services with ``supports_dcr=True`` use
RFC 7591 Dynamic Client Registration (the MCP server issues its own
credentials); the rest use pre-configured credentials via env vars.

``allowed_tools`` whitelists which MCP tools to expose to the agent.
An empty list means "load every tool the server advertises" (used for
user-managed generic MCP servers).  Service-specific entries should
curate this list to keep the agent's tool count low and selection
accuracy high.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.db import SearchSourceConnectorType

# Linear hosted MCP (https://linear.app/docs/mcp). Tool names are matched at
# discovery time: names the server does not advertise are ignored.
# See also https://github.com/linear/linear/issues/1049 for server-reported names.
LINEAR_MCP_WRITE_TOOL_NAMES: frozenset[str] = frozenset({"save_issue"})
LINEAR_MCP_READONLY_TOOL_NAMES: frozenset[str] = frozenset(
    {
        # Issues
        "list_issues",
        "get_issue",
        "list_my_issues",
        "list_issue_statuses",
        "list_issue_labels",
        "list_comments",
        # People & teams
        "list_users",
        "get_user",
        "list_teams",
        "get_team",
        # Projects & planning
        "list_projects",
        "get_project",
        "list_project_labels",
        "list_cycles",
        # Documents
        "list_documents",
        "get_document",
        # Misc read
        "search_documentation",
    }
)
LINEAR_MCP_TOOL_NAMES: frozenset[str] = (
    LINEAR_MCP_READONLY_TOOL_NAMES | LINEAR_MCP_WRITE_TOOL_NAMES
)
_LINEAR_MCP_PREFIXED_NAME_RE = re.compile(r"^linear_\d+_(.+)$")


def linear_mcp_original_tool_name(name: str) -> str | None:
    """Map ``linear_<connector_id>_<tool>`` or bare MCP tool name to base name."""
    m = _LINEAR_MCP_PREFIXED_NAME_RE.match(name)
    if m:
        base = m.group(1)
        return base if base in LINEAR_MCP_TOOL_NAMES else None
    if name in LINEAR_MCP_TOOL_NAMES:
        return name
    return None


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
    allowed_tools: list[str] = field(default_factory=list)
    readonly_tools: frozenset[str] = field(default_factory=frozenset)
    account_metadata_keys: list[str] = field(default_factory=list)
    """``connector.config`` keys exposed by ``get_connected_accounts``.

    Only listed keys are returned to the LLM — tokens and secrets are
    never included.  Every service should at least have its
    ``display_name`` populated during OAuth; additional service-specific
    fields (e.g. Jira ``cloud_id``) are listed here so the LLM can pass
    them to action tools.
    """


MCP_SERVICES: dict[str, MCPServiceConfig] = {
    "linear": MCPServiceConfig(
        name="Linear",
        mcp_url="https://mcp.linear.app/mcp",
        connector_type="LINEAR_CONNECTOR",
        allowed_tools=sorted(LINEAR_MCP_TOOL_NAMES),
        readonly_tools=LINEAR_MCP_READONLY_TOOL_NAMES,
        account_metadata_keys=["organization_name", "organization_url_key"],
    ),
    "jira": MCPServiceConfig(
        name="Jira",
        mcp_url="https://mcp.atlassian.com/v1/mcp",
        connector_type="JIRA_CONNECTOR",
        allowed_tools=[
            "getAccessibleAtlassianResources",
            "searchJiraIssuesUsingJql",
            "getVisibleJiraProjects",
            "getJiraProjectIssueTypesMetadata",
            "createJiraIssue",
            "editJiraIssue",
        ],
        readonly_tools=frozenset(
            {
                "getAccessibleAtlassianResources",
                "searchJiraIssuesUsingJql",
                "getVisibleJiraProjects",
                "getJiraProjectIssueTypesMetadata",
            }
        ),
        account_metadata_keys=["cloud_id", "site_name", "base_url"],
    ),
    "clickup": MCPServiceConfig(
        name="ClickUp",
        mcp_url="https://mcp.clickup.com/mcp",
        connector_type="CLICKUP_CONNECTOR",
        allowed_tools=[
            "clickup_search",
            "clickup_get_task",
        ],
        readonly_tools=frozenset({"clickup_search", "clickup_get_task"}),
        account_metadata_keys=["workspace_id", "workspace_name"],
    ),
    "slack": MCPServiceConfig(
        name="Slack",
        mcp_url="https://mcp.slack.com/mcp",
        connector_type="SLACK_CONNECTOR",
        supports_dcr=False,
        client_id_env="SLACK_CLIENT_ID",
        client_secret_env="SLACK_CLIENT_SECRET",
        auth_endpoint_override="https://slack.com/oauth/v2_user/authorize",
        token_endpoint_override="https://slack.com/api/oauth.v2.user.access",
        scopes=[
            "search:read.public",
            "search:read.private",
            "search:read.mpim",
            "search:read.im",
            "channels:history",
            "groups:history",
            "mpim:history",
            "im:history",
        ],
        allowed_tools=[
            "slack_search_channels",
            "slack_read_channel",
            "slack_read_thread",
        ],
        readonly_tools=frozenset(
            {"slack_search_channels", "slack_read_channel", "slack_read_thread"}
        ),
        # TODO: oauth.v2.user.access only returns team.id, not team.name.
        # To populate team_name, either add "team:read" scope and call
        # GET /api/team.info during OAuth callback, or switch to oauth.v2.access.
        account_metadata_keys=["team_id", "team_name"],
    ),
    "airtable": MCPServiceConfig(
        name="Airtable",
        mcp_url="https://mcp.airtable.com/mcp",
        connector_type="AIRTABLE_CONNECTOR",
        supports_dcr=False,
        oauth_discovery_origin="https://airtable.com",
        client_id_env="AIRTABLE_CLIENT_ID",
        client_secret_env="AIRTABLE_CLIENT_SECRET",
        scopes=["data.records:read", "schema.bases:read"],
        allowed_tools=[
            "list_bases",
            "list_tables_for_base",
            "list_records_for_table",
        ],
        readonly_tools=frozenset(
            {"list_bases", "list_tables_for_base", "list_records_for_table"}
        ),
        account_metadata_keys=["user_id", "user_email"],
    ),
}

_CONNECTOR_TYPE_TO_SERVICE: dict[str, MCPServiceConfig] = {
    svc.connector_type: svc for svc in MCP_SERVICES.values()
}

LIVE_CONNECTOR_TYPES: frozenset[SearchSourceConnectorType] = frozenset(
    {
        SearchSourceConnectorType.SLACK_CONNECTOR,
        SearchSourceConnectorType.TEAMS_CONNECTOR,
        SearchSourceConnectorType.LINEAR_CONNECTOR,
        SearchSourceConnectorType.JIRA_CONNECTOR,
        SearchSourceConnectorType.CLICKUP_CONNECTOR,
        SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
        SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
        SearchSourceConnectorType.AIRTABLE_CONNECTOR,
        SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR,
        SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
        SearchSourceConnectorType.DISCORD_CONNECTOR,
        SearchSourceConnectorType.LUMA_CONNECTOR,
    }
)


def get_service(key: str) -> MCPServiceConfig | None:
    return MCP_SERVICES.get(key)


def get_service_by_connector_type(connector_type: str) -> MCPServiceConfig | None:
    """Look up an MCP service config by its ``connector_type`` enum value."""
    return _CONNECTOR_TYPE_TO_SERVICE.get(connector_type)
