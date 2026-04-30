"""Gate supervisor routing tools by connected searchable connector types (aligned with ``new_chat`` KB).

When ``available_connectors`` is ``None``, all routes are emitted (caller did not pass an inventory).

When provided, a connector route is emitted only if at least one required searchable type is present.
MCP tools are filtered upstream in :func:`~app.agents.multi_agent_chat.core.mcp_partition.partition_mcp_tools_by_expert_route`
so merges only include tools for connected accounts.
"""

from __future__ import annotations

# Route tool_name → searchable connector / doc-type strings (same family as
# ``chat_deepagent._CONNECTOR_TYPE_TO_SEARCHABLE`` values in ``available_connectors``).
_ROUTE_REQUIRES_ANY: dict[str, frozenset[str]] = {
    "calendar": frozenset(
        {"GOOGLE_CALENDAR_CONNECTOR", "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR"}
    ),
    "confluence": frozenset({"CONFLUENCE_CONNECTOR"}),
    "discord": frozenset({"DISCORD_CONNECTOR"}),
    "dropbox": frozenset({"DROPBOX_FILE"}),
    "gmail": frozenset({"GOOGLE_GMAIL_CONNECTOR", "COMPOSIO_GMAIL_CONNECTOR"}),
    "google_drive": frozenset(
        {"GOOGLE_DRIVE_FILE", "COMPOSIO_GOOGLE_DRIVE_CONNECTOR"}
    ),
    "luma": frozenset({"LUMA_CONNECTOR"}),
    "notion": frozenset({"NOTION_CONNECTOR"}),
    "onedrive": frozenset({"ONEDRIVE_FILE"}),
    "teams": frozenset({"TEAMS_CONNECTOR"}),
    # MCP-only supervisor routes (see ``core.mcp_partition.MCP_ONLY_ROUTE_KEYS_IN_ORDER``).
    "linear": frozenset({"LINEAR_CONNECTOR"}),
    "slack": frozenset({"SLACK_CONNECTOR"}),
    "jira": frozenset({"JIRA_CONNECTOR"}),
    "clickup": frozenset({"CLICKUP_CONNECTOR"}),
    "airtable": frozenset({"AIRTABLE_CONNECTOR"}),
    "generic_mcp": frozenset({"MCP_CONNECTOR"}),
}


def include_connector_route(
    route_key: str,
    available_connectors: list[str] | None,
) -> bool:
    """Return whether to register this connector route on the supervisor.

    If ``available_connectors`` is omitted, preserve legacy behaviour (emit the route).

    Otherwise require at least one matching entry in ``available_connectors`` for connector-backed routes.
    Builtin routes (research, memory, …) have no entry in ``_ROUTE_REQUIRES_ANY`` and are always included.
    """
    if available_connectors is None:
        return True
    required = _ROUTE_REQUIRES_ANY.get(route_key)
    if required is None:
        return True
    avail = set(available_connectors)
    return bool(required & avail)
