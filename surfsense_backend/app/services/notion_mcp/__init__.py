"""Notion MCP integration.

Routes Notion operations through Notion's hosted MCP server
at https://mcp.notion.com/mcp instead of direct API calls.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSourceConnector, SearchSourceConnectorType


async def has_mcp_notion_connector(
    session: AsyncSession,
    search_space_id: int,
) -> bool:
    """Check whether the search space has at least one MCP-mode Notion connector."""
    result = await session.execute(
        select(SearchSourceConnector.id, SearchSourceConnector.config).filter(
            SearchSourceConnector.search_space_id == search_space_id,
            SearchSourceConnector.connector_type == SearchSourceConnectorType.NOTION_CONNECTOR,
        )
    )
    for _, config in result.all():
        if isinstance(config, dict) and config.get("mcp_mode"):
            return True
    return False
