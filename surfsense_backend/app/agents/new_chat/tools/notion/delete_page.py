import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.notion_history import NotionHistoryConnector
from app.services.notion.tool_metadata_service import NotionToolMetadataService

logger = logging.getLogger(__name__)


def create_delete_notion_page_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    """
    Factory function to create the delete_notion_page tool.

    Args:
        db_session: Database session for accessing Notion connector
        search_space_id: Search space ID to find the Notion connector
        user_id: User ID for finding the correct Notion connector
        connector_id: Optional specific connector ID (if known)

    Returns:
        Configured delete_notion_page tool
    """

    @tool
    async def delete_notion_page(
        page_title: str,
    ) -> dict[str, Any]:
        """Delete (archive) a Notion page.

        Use this tool when the user asks you to delete, remove, or archive
        a Notion page. Note that Notion doesn't permanently delete pages,
        it archives them (they can be restored from trash).

        Args:
            page_title: The title of the Notion page to delete.

        Returns:
            Dictionary with:
            - status: "success" or "error"
            - page_id: Deleted page ID
            - message: Success or error message

        Examples:
            - "Delete the 'Meeting Notes' Notion page"
            - "Remove the 'Old Project Plan' Notion page"
            - "Archive the 'Draft Ideas' Notion page"
        """
        logger.info(f"delete_notion_page called: page_title='{page_title}'")
        
        if db_session is None or search_space_id is None or user_id is None:
            logger.error("Notion tool not properly configured - missing required parameters")
            return {
                "status": "error",
                "message": "Notion tool not properly configured. Please contact support.",
            }

        try:
            # Get page context (page_id, account, title) from indexed data
            metadata_service = NotionToolMetadataService(db_session)
            context = await metadata_service.get_delete_context(
                search_space_id, user_id, page_title
            )

            if "error" in context:
                error_msg = context["error"]
                # Check if it's a "not found" error (softer handling for LLM)
                if "not found" in error_msg.lower():
                    logger.warning(f"Page not found: {error_msg}")
                    return {
                        "status": "not_found",
                        "message": error_msg,
                    }
                else:
                    logger.error(f"Failed to fetch delete context: {error_msg}")
                    return {
                        "status": "error",
                        "message": error_msg,
                    }

            page_id = context.get("page_id")
            connector_id_from_context = context.get("account", {}).get("id")

            logger.info(f"Requesting approval for deleting Notion page: '{page_title}' (page_id={page_id})")
            # Request approval before deleting
            approval = interrupt(
                {
                    "type": "notion_page_deletion",
                    "action": {
                        "tool": "delete_notion_page",
                        "params": {
                            "page_id": page_id,
                            "connector_id": connector_id_from_context,
                        },
                    },
                    "context": context,
                }
            )

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
                logger.info("Notion page deletion rejected by user")
                return {
                    "status": "rejected",
                    "message": "User declined. The page was not deleted. Do not ask again or suggest alternatives.",
                }

            logger.info(f"Deleting Notion page: page_id={page_id}")

            # Create connector instance
            notion_connector = NotionHistoryConnector(
                session=db_session,
                connector_id=connector_id_from_context,
            )

            # Delete the page
            result = await notion_connector.delete_page(page_id=page_id)
            logger.info(f"delete_page result: {result.get('status')} - {result.get('message', '')}")
            return result

        except ValueError as e:
            logger.error(f"ValueError in delete_notion_page: {e}")
            return {
                "status": "error",
                "message": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error in delete_notion_page: {e}")
            return {
                "status": "error",
                "message": f"Unexpected error deleting Notion page: {e!s}",
            }

    return delete_notion_page
