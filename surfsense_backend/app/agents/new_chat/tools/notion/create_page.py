import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.notion_history import NotionHistoryConnector
from app.services.notion import NotionToolMetadataService

logger = logging.getLogger(__name__)


def create_create_notion_page_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    """
    Factory function to create the create_notion_page tool.

    Args:
        db_session: Database session for accessing Notion connector
        search_space_id: Search space ID to find the Notion connector
        user_id: User ID for fetching user-specific context
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
        logger.info(f"create_notion_page called: title='{title}', parent_page_id={parent_page_id}")
        
        if db_session is None or search_space_id is None or user_id is None:
            logger.error("Notion tool not properly configured - missing required parameters")
            return {
                "status": "error",
                "message": "Notion tool not properly configured. Please contact support.",
            }

        try:
            metadata_service = NotionToolMetadataService(db_session)
            context = await metadata_service.get_creation_context(search_space_id, user_id)
            
            if "error" in context:
                logger.error(f"Failed to fetch creation context: {context['error']}")
                return {
                    "status": "error",
                    "message": context["error"],
                }
            
            logger.info("Requesting approval for creating Notion page")
            approval = interrupt({
                "type": "notion_page_creation",
                "message": f"Approve creating Notion page: '{title}'",
                "action": {
                    "tool": "create_notion_page",
                    "params": {
                        "title": title,
                        "content": content,
                        "parent_page_id": parent_page_id,
                        "connector_id": connector_id,
                    },
                },
                "context": context,
            })
            
            decisions = approval.get("decisions", [])
            if not decisions:
                logger.warning("No approval decision received")
                return {
                    "status": "error",
                    "message": "No approval decision received",
                }
            
            decision = decisions[0]
            decision_type = decision.get("decision_type")
            
            if decision_type == "reject":
                logger.info("Notion page creation rejected by user")
                return {
                    "status": "rejected",
                    "message": "Page creation was rejected",
                }
            
            edited_action = decision.get("edited_action", {})
            final_params = edited_action if edited_action else {
                "title": title,
                "content": content,
                "parent_page_id": parent_page_id,
                "connector_id": connector_id,
            }
            
            final_title = final_params.get("title", title)
            final_content = final_params.get("content", content)
            final_parent_page_id = final_params.get("parent_page_id", parent_page_id)
            final_connector_id = final_params.get("connector_id", connector_id)
            
            logger.info(f"Creating Notion page with final params: title='{final_title}'")
            
            actual_connector_id = final_connector_id
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
                    logger.warning(f"No Notion connector found for search_space_id={search_space_id}")
                    return {
                        "status": "error",
                        "message": "No Notion connector found. Please connect Notion in your workspace settings.",
                    }

                actual_connector_id = connector.id
                logger.info(f"Found Notion connector: id={actual_connector_id}")

            notion_connector = NotionHistoryConnector(
                session=db_session,
                connector_id=actual_connector_id,
            )

            result = await notion_connector.create_page(
                title=final_title,
                content=final_content,
                parent_page_id=final_parent_page_id,
            )
            logger.info(f"create_page result: {result.get('status')} - {result.get('message', '')}")
            return result

        except Exception as e:
            from langgraph.errors import GraphInterrupt
            
            if isinstance(e, GraphInterrupt):
                raise
            
            logger.error(f"Error creating Notion page: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e) if isinstance(e, ValueError) else f"Unexpected error: {e!s}",
            }

    return create_notion_page
