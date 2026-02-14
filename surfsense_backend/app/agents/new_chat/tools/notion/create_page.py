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
            - status: "success", "rejected", or "error"
            - page_id: Created page ID (if success)
            - url: URL to the created page (if success)
            - title: Page title (if success)
            - message: Result message
            
            IMPORTANT: If status is "rejected", the user explicitly declined the action.
            Respond with a brief acknowledgment (e.g., "Understood, I didn't create the page.") 
            and move on. Do NOT ask for parent page IDs, troubleshoot, or suggest alternatives.

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
            
            logger.info(f"Requesting approval for creating Notion page: '{title}'")
            approval = interrupt({
                "type": "notion_page_creation",
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
            decision_type = decision.get("type") or decision.get("decision_type")
            logger.info(f"User decision: {decision_type}")
            
            if decision_type == "reject":
                logger.info("Notion page creation rejected by user")
                return {
                    "status": "rejected",
                    "message": "User declined. The page was not created. Do not ask again or suggest alternatives.",
                }
            
            edited_action = decision.get("edited_action", {})
            final_params = edited_action.get("args", {}) if edited_action else {}
            
            final_title = final_params.get("title", title)
            final_content = final_params.get("content", content)
            final_parent_page_id = final_params.get("parent_page_id", parent_page_id)
            final_connector_id = final_params.get("connector_id", connector_id)
            
            if not final_title or not final_title.strip():
                logger.error("Title is empty or contains only whitespace")
                return {
                    "status": "error",
                    "message": "Page title cannot be empty. Please provide a valid title.",
                }
            
            logger.info(f"Creating Notion page with final params: title='{final_title}'")
            
            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            actual_connector_id = final_connector_id
            if actual_connector_id is None:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
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
            else:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == actual_connector_id,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.NOTION_CONNECTOR,
                    )
                )
                connector = result.scalars().first()

                if not connector:
                    logger.error(
                        f"Invalid connector_id={actual_connector_id} for search_space_id={search_space_id}"
                    )
                    return {
                        "status": "error",
                        "message": "Selected Notion account is invalid or has been disconnected. Please select a valid account.",
                    }
                logger.info(f"Validated Notion connector: id={actual_connector_id}")

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
