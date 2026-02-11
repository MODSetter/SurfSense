from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.notion_history import NotionHistoryConnector


def create_create_notion_page_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    connector_id: int | None = None,
):
    """
    Factory function to create the create_notion_page tool.

    Args:
        db_session: Database session for accessing Notion connector
        search_space_id: Search space ID to find the Notion connector
        connector_id: Optional specific connector ID (if known)

    Returns:
        Configured create_notion_page tool
    """

    @tool
    async def create_notion_page(
        title: str,
        content: str,
        parent_page_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new page in Notion with the given title and content.

        Use this tool when the user asks you to create, save, or publish
        something to Notion. The page will be created in the user's
        configured Notion workspace.

        Args:
            title: The title of the Notion page.
            content: The markdown content for the page body (supports headings, lists, paragraphs).
            parent_page_id: Optional parent page ID to create as a subpage.
                           If not provided, will ask for one.

        Returns:
            Dictionary with:
            - status: "success" or "error"
            - page_id: Created page ID
            - url: URL to the created page
            - title: Page title
            - message: Success or error message

        Examples:
            - "Create a Notion page titled 'Meeting Notes' with content 'Discussed project timeline'"
            - "Save this to Notion with title 'Research Summary'"
        """
        if db_session is None or search_space_id is None:
            return {
                "status": "error",
                "message": "Notion tool not properly configured. Please contact support.",
            }

        try:
            # Get connector ID if not provided
            if connector_id is None:
                from sqlalchemy.future import select

                from app.db import SearchSourceConnector, SearchSourceConnectorType

                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.NOTION_CONNECTOR,
                        SearchSourceConnector.is_enabled == True,
                    )
                )
                connector = result.scalars().first()

                if not connector:
                    return {
                        "status": "error",
                        "message": "No Notion connector found. Please connect Notion in your workspace settings.",
                    }

                connector_id = connector.id

            # Create connector instance
            notion_connector = NotionHistoryConnector(
                session=db_session,
                connector_id=connector_id,
            )

            # Create the page
            result = await notion_connector.create_page(
                title=title, content=content, parent_page_id=parent_page_id
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
                "message": f"Unexpected error creating Notion page: {str(e)}",
            }

    return create_notion_page
