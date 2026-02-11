from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.notion_history import NotionHistoryConnector


def create_delete_notion_page_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    connector_id: int | None = None,
):
    """
    Factory function to create the delete_notion_page tool.

    Args:
        db_session: Database session for accessing Notion connector
        search_space_id: Search space ID to find the Notion connector
        connector_id: Optional specific connector ID (if known)

    Returns:
        Configured delete_notion_page tool
    """

    @tool
    async def delete_notion_page(
        page_id: str,
    ) -> dict[str, Any]:
        """Delete (archive) a Notion page.

        Use this tool when the user asks you to delete, remove, or archive
        a Notion page. Note that Notion doesn't permanently delete pages,
        it archives them (they can be restored from trash).

        Args:
            page_id: The ID of the Notion page to delete (required).

        Returns:
            Dictionary with:
            - status: "success" or "error"
            - page_id: Deleted page ID
            - message: Success or error message

        Examples:
            - "Delete the Notion page abc123"
            - "Remove the page xyz789 from Notion"
            - "Archive this Notion page: abc123"
        """
        if db_session is None or search_space_id is None:
            return {
                "status": "error",
                "message": "Notion tool not properly configured. Please contact support.",
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

            # Delete the page
            result = await notion_connector.delete_page(page_id=page_id)
            return result

        except ValueError as e:
            return {
                "status": "error",
                "message": str(e),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Unexpected error deleting Notion page: {e!s}",
            }

    return delete_notion_page
