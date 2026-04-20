import logging
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.hitl import request_approval
from app.services.notion.tool_metadata_service import NotionToolMetadataService

logger = logging.getLogger(__name__)


def create_delete_notion_page_mcp_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    @tool
    async def delete_notion_page(
        page_title: str,
        delete_from_kb: bool = False,
    ) -> dict[str, Any]:
        """Delete (archive) a Notion page.

        Use this tool when the user asks you to delete, remove, or archive
        a Notion page. Note that Notion doesn't permanently delete pages,
        it archives them (they can be restored from trash).

        Args:
            page_title: The title of the Notion page to delete.
            delete_from_kb: Whether to also remove the page from the knowledge base.
                          Default is False.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "not_found", or "error"
            - page_id: Deleted page ID (if success)
            - message: Success or error message
            - deleted_from_kb: Whether the page was also removed from knowledge base (if success)

        Examples:
            - "Delete the 'Meeting Notes' Notion page"
            - "Remove the 'Old Project Plan' Notion page"
        """
        logger.info(
            "delete_notion_page (MCP) called: page_title='%s', delete_from_kb=%s",
            page_title,
            delete_from_kb,
        )

        if db_session is None or search_space_id is None or user_id is None:
            logger.error("Notion MCP tool not properly configured - missing required parameters")
            return {
                "status": "error",
                "message": "Notion tool not properly configured. Please contact support.",
            }

        try:
            metadata_service = NotionToolMetadataService(db_session)
            context = await metadata_service.get_delete_context(search_space_id, user_id, page_title)

            if "error" in context:
                error_msg = context["error"]
                if "not found" in error_msg.lower():
                    return {"status": "not_found", "message": error_msg}
                return {"status": "error", "message": error_msg}

            account = context.get("account", {})
            if account.get("auth_expired"):
                return {
                    "status": "auth_error",
                    "message": "The Notion account for this page needs re-authentication. Please re-authenticate in your connector settings.",
                }

            page_id = context.get("page_id")
            connector_id_from_context = account.get("id")
            document_id = context.get("document_id")

            result = request_approval(
                action_type="notion_page_deletion",
                tool_name="delete_notion_page",
                params={
                    "page_id": page_id,
                    "connector_id": connector_id_from_context,
                    "delete_from_kb": delete_from_kb,
                },
                context=context,
            )

            if result.rejected:
                logger.info("Notion page deletion rejected by user")
                return {
                    "status": "rejected",
                    "message": "User declined. Do not retry or suggest alternatives.",
                }

            final_page_id = result.params.get("page_id", page_id)
            final_connector_id = result.params.get("connector_id", connector_id_from_context)
            final_delete_from_kb = result.params.get("delete_from_kb", delete_from_kb)

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            if final_connector_id:
                query_result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == final_connector_id,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type == SearchSourceConnectorType.NOTION_CONNECTOR,
                    )
                )
                connector = query_result.scalars().first()
                if not connector:
                    return {
                        "status": "error",
                        "message": "Selected Notion account is invalid or has been disconnected.",
                    }
                actual_connector_id = connector.id
            else:
                return {"status": "error", "message": "No connector found for this page."}

            from app.services.notion_mcp.adapter import NotionMCPAdapter

            adapter = NotionMCPAdapter(session=db_session, connector_id=actual_connector_id)
            result = await adapter.delete_page(page_id=final_page_id)
            logger.info("delete_page (MCP) result: %s - %s", result.get("status"), result.get("message", ""))

            deleted_from_kb = False
            if result.get("status") == "success" and final_delete_from_kb and document_id:
                try:
                    from sqlalchemy.future import select

                    from app.db import Document

                    doc_result = await db_session.execute(
                        select(Document).filter(Document.id == document_id)
                    )
                    document = doc_result.scalars().first()

                    if document:
                        await db_session.delete(document)
                        await db_session.commit()
                        deleted_from_kb = True
                        logger.info("Deleted document %s from knowledge base", document_id)
                except Exception as e:
                    logger.error("Failed to delete document from KB: %s", e)
                    await db_session.rollback()
                    result["warning"] = f"Page deleted from Notion, but failed to remove from knowledge base: {e!s}"

            if result.get("status") == "success":
                result["deleted_from_kb"] = deleted_from_kb
                if deleted_from_kb:
                    result["message"] = f"{result.get('message', '')} (also removed from knowledge base)"

            return result

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error("Error deleting Notion page (MCP): %s", e, exc_info=True)
            if isinstance(e, ValueError):
                message = str(e)
            else:
                message = "Something went wrong while deleting the page. Please try again."
            return {"status": "error", "message": message}

    return delete_notion_page
