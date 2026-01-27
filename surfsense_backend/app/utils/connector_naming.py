"""
Connector Naming Utilities.

Provides functions for generating unique, user-friendly connector names.
"""

from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.db import SearchSourceConnector, SearchSourceConnectorType

# Friendly display names for connector types
BASE_NAME_FOR_TYPE = {
    SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR: "Gmail",
    SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR: "Google Drive",
    SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR: "Google Calendar",
    SearchSourceConnectorType.SLACK_CONNECTOR: "Slack",
    SearchSourceConnectorType.TEAMS_CONNECTOR: "Microsoft Teams",
    SearchSourceConnectorType.NOTION_CONNECTOR: "Notion",
    SearchSourceConnectorType.LINEAR_CONNECTOR: "Linear",
    SearchSourceConnectorType.JIRA_CONNECTOR: "Jira",
    SearchSourceConnectorType.DISCORD_CONNECTOR: "Discord",
    SearchSourceConnectorType.CONFLUENCE_CONNECTOR: "Confluence",
    SearchSourceConnectorType.AIRTABLE_CONNECTOR: "Airtable",
    SearchSourceConnectorType.MCP_CONNECTOR: "Model Context Protocol (MCP)",
    SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR: "Gmail",
    SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR: "Google Drive",
    SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR: "Google Calendar",
}


def get_base_name_for_type(connector_type: SearchSourceConnectorType) -> str:
    """Get a friendly display name for a connector type."""
    return BASE_NAME_FOR_TYPE.get(
        connector_type, connector_type.replace("_", " ").title()
    )


def extract_identifier_from_credentials(
    connector_type: SearchSourceConnectorType,
    credentials: dict[str, Any],
) -> str | None:
    """
    Extract a unique identifier from connector credentials.

    Args:
        connector_type: The type of connector
        credentials: The connector credentials dict

    Returns:
        Identifier string (workspace name, email, etc.) or None
    """
    if connector_type == SearchSourceConnectorType.SLACK_CONNECTOR:
        return credentials.get("team_name")

    if connector_type == SearchSourceConnectorType.TEAMS_CONNECTOR:
        return credentials.get("tenant_name")

    if connector_type == SearchSourceConnectorType.NOTION_CONNECTOR:
        return credentials.get("workspace_name")

    if connector_type == SearchSourceConnectorType.DISCORD_CONNECTOR:
        return credentials.get("guild_name")

    if connector_type in (
        SearchSourceConnectorType.JIRA_CONNECTOR,
        SearchSourceConnectorType.CONFLUENCE_CONNECTOR,
    ):
        base_url = credentials.get("base_url", "")
        if base_url:
            try:
                parsed = urlparse(base_url)
                hostname = parsed.netloc or parsed.path
                if ".atlassian.net" in hostname:
                    return hostname.replace(".atlassian.net", "")
                return hostname
            except (ValueError, TypeError, AttributeError):
                pass
        return None

    # Google, Linear, Airtable require API calls - return None
    return None


def generate_connector_name_with_identifier(
    connector_type: SearchSourceConnectorType,
    identifier: str | None,
) -> str:
    """
    Generate a connector name with an identifier.

    Args:
        connector_type: The type of connector
        identifier: User identifier (email, workspace name, etc.)

    Returns:
        Name like "Gmail - john@example.com" or just "Gmail" if no identifier
    """
    base = get_base_name_for_type(connector_type)
    if identifier:
        return f"{base} - {identifier}"
    return base


async def count_connectors_of_type(
    session: AsyncSession,
    connector_type: SearchSourceConnectorType,
    search_space_id: int,
    user_id: UUID,
) -> int:
    """Count existing connectors of a type for a user in a search space."""
    result = await session.execute(
        select(func.count(SearchSourceConnector.id)).where(
            SearchSourceConnector.connector_type == connector_type,
            SearchSourceConnector.search_space_id == search_space_id,
            SearchSourceConnector.user_id == user_id,
        )
    )
    return result.scalar() or 0


async def check_duplicate_connector(
    session: AsyncSession,
    connector_type: SearchSourceConnectorType,
    search_space_id: int,
    user_id: UUID,
    identifier: str | None,
) -> bool:
    """
    Check if a connector with the same identifier already exists.

    Args:
        session: Database session
        connector_type: The type of connector
        search_space_id: The search space ID
        user_id: The user ID
        identifier: User identifier (email, workspace name, etc.)

    Returns:
        True if a duplicate exists, False otherwise
    """
    if not identifier:
        return False

    expected_name = f"{get_base_name_for_type(connector_type)} - {identifier}"
    result = await session.execute(
        select(func.count(SearchSourceConnector.id)).where(
            SearchSourceConnector.connector_type == connector_type,
            SearchSourceConnector.search_space_id == search_space_id,
            SearchSourceConnector.user_id == user_id,
            SearchSourceConnector.name == expected_name,
        )
    )
    return (result.scalar() or 0) > 0


async def generate_unique_connector_name(
    session: AsyncSession,
    connector_type: SearchSourceConnectorType,
    search_space_id: int,
    user_id: UUID,
    identifier: str | None = None,
) -> str:
    """
    Generate a unique connector name.

    If an identifier is provided (email, workspace name, etc.), uses it with base name.
    Otherwise, falls back to counting existing connectors for uniqueness.

    Args:
        session: Database session
        connector_type: The type of connector
        search_space_id: The search space ID
        user_id: The user ID
        identifier: Optional user identifier (email, workspace name, etc.)

    Returns:
        Unique name like "Gmail - john@example.com" or "Gmail (2)"
    """
    base = get_base_name_for_type(connector_type)

    if identifier:
        return f"{base} - {identifier}"

    # Fallback: use counter for uniqueness
    count = await count_connectors_of_type(
        session, connector_type, search_space_id, user_id
    )

    if count == 0:
        return base
    return f"{base} ({count + 1})"
