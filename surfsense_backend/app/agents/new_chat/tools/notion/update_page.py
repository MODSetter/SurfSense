from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.notion_history import NotionHistoryConnector


def create_update_notion_page_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    connector_id: int | None = None,
):
    """
    Factory function to create the update_notion_page tool.

    Args:
        db_session: Database session for accessing Notion connector
        search_space_id: Search space ID to find the Notion connector
        connector_id: Optional specific connector ID (if known)

    Returns:
        Configured update_notion_page tool
    """

    @tool
    async def update_notion_page(
        page_id: str,
        title: str | None = None,
        content: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing Notion page's title and/or content.

        Use this tool when the user asks you to modify, edit, or update
        a Notion page. At least one of title or content must be provided.

        Args:
            page_id: The ID of the Notion page to update (required).
            title: New title for the page (optional).
            content: New markdown content for the page body (optional).
                    If provided, replaces all existing content.

        Returns:
            Dictionary with:
            - status: "success" or "error"
            - page_id: Updated page ID
            - url: URL to the updated page
            - title: Current page title
            - message: Success or error message

        Examples:
            - "Update the Notion page abc123 with title 'Updated Meeting Notes'"
            - "Change the content of page xyz789 to 'New content here'"
            - "Update page abc123 with new title 'Final Report' and content '# Summary...'"
        """
        if db_session is None or search_space_id is None:
            return {
                "status": "error",
                "message": "Notion tool not properly configured. Please contact support.",
            }

        if not title and not content:
            return {
                "status": "error",
                "message": "At least one of 'title' or 'content' must be provided to update the page.",
            }

        try:
            # Get connector ID if not provided
            actual_connector_id = connector_id
            if actual_connector_id is None:
                from sqlalchemy.future import select

                from app.db import SearchSourceConnector, SearchSourceConnectorType

                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.NOTION_CONNECTOR,
                    )
                )
                connector = result.scalars().first()

                if not connector:
                    return {
                        "status": "error",
                        "message": "No Notion connector found. Please connect Notion in your workspace settings.",
                    }

                actual_connector_id = connector.id

            # Create connector instance
            notion_connector = NotionHistoryConnector(
                session=db_session,
                connector_id=actual_connector_id,
            )

            # Update the page
            result = await notion_connector.update_page(
                page_id=page_id, title=title, content=content
            )
            return result

        except ValueError as e:
            return {
                "status": "error",
                "message": str(e),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Unexpected error updating Notion page: {e!s}",
            }

    return update_notion_page
