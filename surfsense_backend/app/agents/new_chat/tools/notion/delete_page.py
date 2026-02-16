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
        delete_from_db: bool = False,
    ) -> dict[str, Any]:
        """Delete (archive) a Notion page.

        Use this tool when the user asks you to delete, remove, or archive
        a Notion page. Note that Notion doesn't permanently delete pages,
        it archives them (they can be restored from trash).

        Args:
            page_title: The title of the Notion page to delete.
            delete_from_db: Whether to also remove the page from the knowledge base.
                          Default is False (in Notion).
                          Set to True to permanently remove from both Notion and knowledge base.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "not_found", or "error"
            - page_id: Deleted page ID (if success)
            - message: Success or error message
            - deleted_from_db: Whether the page was also removed from knowledge base (if success)

        Examples:
            - "Delete the 'Meeting Notes' Notion page"
            - "Remove the 'Old Project Plan' Notion page"
            - "Archive the 'Draft Ideas' Notion page"
        """
        logger.info(
            f"delete_notion_page called: page_title='{page_title}', delete_from_db={delete_from_db}"
        )

        if db_session is None or search_space_id is None or user_id is None:
            logger.error(
                "Notion tool not properly configured - missing required parameters"
            )
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
            document_id = context.get("document_id")

            logger.info(
                f"Requesting approval for deleting Notion page: '{page_title}' (page_id={page_id}, delete_from_db={delete_from_db})"
            )

            # Request approval before deleting
            approval = interrupt(
                {
                    "type": "notion_page_deletion",
                    "action": {
                        "tool": "delete_notion_page",
                        "params": {
                            "page_id": page_id,
                            "connector_id": connector_id_from_context,
                            "delete_from_db": delete_from_db,
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

            # Extract edited action arguments (if user modified the checkbox)
            edited_action = decision.get("edited_action", {})
            final_params = edited_action.get("args", {}) if edited_action else {}

            final_page_id = final_params.get("page_id", page_id)
            final_connector_id = final_params.get(
                "connector_id", connector_id_from_context
            )
            final_delete_from_db = final_params.get("delete_from_db", delete_from_db)

            logger.info(
                f"Deleting Notion page with final params: page_id={final_page_id}, connector_id={final_connector_id}, delete_from_db={final_delete_from_db}"
            )

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            # Validate the connector
            if final_connector_id:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == final_connector_id,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.NOTION_CONNECTOR,
                    )
                )
                connector = result.scalars().first()

                if not connector:
                    logger.error(
                        f"Invalid connector_id={final_connector_id} for search_space_id={search_space_id}"
                    )
                    return {
                        "status": "error",
                        "message": "Selected Notion account is invalid or has been disconnected. Please select a valid account.",
                    }
                actual_connector_id = connector.id
                logger.info(f"Validated Notion connector: id={actual_connector_id}")
            else:
                logger.error("No connector found for this page")
                return {
                    "status": "error",
                    "message": "No connector found for this page.",
                }

            # Create connector instance
            notion_connector = NotionHistoryConnector(
                session=db_session,
                connector_id=actual_connector_id,
            )

            # Delete the page from Notion
            result = await notion_connector.delete_page(page_id=final_page_id)
            logger.info(
                f"delete_page result: {result.get('status')} - {result.get('message', '')}"
            )

            # If deletion was successful and user wants to delete from DB
            deleted_from_db = False
            if (
                result.get("status") == "success"
                and final_delete_from_db
                and document_id
            ):
                try:
                    from sqlalchemy.future import select

                    from app.db import Document

                    # Get the document
                    doc_result = await db_session.execute(
                        select(Document).filter(Document.id == document_id)
                    )
                    document = doc_result.scalars().first()

                    if document:
                        await db_session.delete(document)
                        await db_session.commit()
                        deleted_from_db = True
                        logger.info(
                            f"Deleted document {document_id} from knowledge base"
                        )
                    else:
                        logger.warning(f"Document {document_id} not found in DB")
                except Exception as e:
                    logger.error(f"Failed to delete document from DB: {e}")
                    # Don't fail the whole operation if DB deletion fails
                    # The page is already deleted from Notion, so inform the user
                    result["warning"] = (
                        f"Page deleted from Notion, but failed to remove from knowledge base: {e!s}"
                    )

            # Update result with DB deletion status
            if result.get("status") == "success":
                result["deleted_from_db"] = deleted_from_db
                if deleted_from_db:
                    result["message"] = (
                        f"{result.get('message', '')} (also removed from knowledge base)"
                    )

            return result

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error deleting Notion page: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
                if isinstance(e, ValueError)
                else f"Unexpected error: {e!s}",
            }

    return delete_notion_page
