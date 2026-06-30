import logging
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.receipts.command import with_receipt
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import make_receipt
from app.agents.chat.multi_agent_chat.subagents.shared.hitl.approvals.self_gated import (
    request_approval,
)
from app.connectors.notion_history import NotionAPIError, NotionHistoryConnector
from app.services.notion.tool_metadata_service import NotionToolMetadataService

logger = logging.getLogger(__name__)


def create_delete_notion_page_tool(
    db_session: AsyncSession | None = None,
    workspace_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    """
    Factory function to create the delete_notion_page tool.

    Args:
        db_session: Database session for accessing Notion connector
        workspace_id: Workspace ID to find the Notion connector
        user_id: User ID for finding the correct Notion connector
        connector_id: Optional specific connector ID (if known)

    Returns:
        Configured delete_notion_page tool
    """

    @tool
    async def delete_notion_page(
        page_title: str,
        runtime: ToolRuntime,
        delete_from_kb: bool = False,
    ) -> Command:
        """Delete (archive) a Notion page.

        Use this tool when the user asks you to delete, remove, or archive
        a Notion page. Note that Notion doesn't permanently delete pages,
        it archives them (they can be restored from trash).

        Args:
            page_title: The title of the Notion page to delete.
            delete_from_kb: Whether to also remove the page from the knowledge base.
                          Default is False.
                          Set to True to permanently remove from both Notion and knowledge base.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "not_found", or "error"
            - page_id: Deleted page ID (if success)
            - message: Success or error message
            - deleted_from_kb: Whether the page was also removed from knowledge base (if success)

        Examples:
            - "Delete the 'Meeting Notes' Notion page"
            - "Remove the 'Old Project Plan' Notion page"
            - "Archive the 'Draft Ideas' Notion page"
        """
        logger.info(
            f"delete_notion_page called: page_title='{page_title}', delete_from_kb={delete_from_kb}"
        )

        def _emit(
            payload: dict[str, Any],
            *,
            status: str,
            external_id: str | None = None,
            error: str | None = None,
        ) -> Command:
            return with_receipt(
                payload=payload,
                receipt=make_receipt(
                    route="notion",
                    type="page",
                    operation="delete",
                    status="success" if status == "success" else "failed",
                    external_id=external_id,
                    preview=page_title,
                    error=error,
                ),
                tool_call_id=runtime.tool_call_id,
            )

        if db_session is None or workspace_id is None or user_id is None:
            logger.error(
                "Notion tool not properly configured - missing required parameters"
            )
            return _emit(
                {
                    "status": "error",
                    "message": "Notion tool not properly configured. Please contact support.",
                },
                status="error",
                error="Notion tool not properly configured. Please contact support.",
            )

        try:
            # Get page context (page_id, account, title) from indexed data
            metadata_service = NotionToolMetadataService(db_session)
            context = await metadata_service.get_delete_context(
                workspace_id, user_id, page_title
            )

            if "error" in context:
                error_msg = context["error"]
                # Check if it's a "not found" error (softer handling for LLM)
                if "not found" in error_msg.lower():
                    logger.warning(f"Page not found: {error_msg}")
                    return _emit(
                        {"status": "not_found", "message": error_msg},
                        status="error",
                        error=error_msg,
                    )
                else:
                    logger.error(f"Failed to fetch delete context: {error_msg}")
                    return _emit(
                        {"status": "error", "message": error_msg},
                        status="error",
                        error=error_msg,
                    )

            account = context.get("account", {})
            if account.get("auth_expired"):
                logger.warning(
                    "Notion account %s has expired authentication",
                    account.get("id"),
                )
                return _emit(
                    {
                        "status": "auth_error",
                        "message": "The Notion account for this page needs re-authentication. Please re-authenticate in your connector settings.",
                    },
                    status="error",
                    error="auth_expired",
                )

            page_id = context.get("page_id")
            connector_id_from_context = account.get("id")
            document_id = context.get("document_id")

            logger.info(
                f"Requesting approval for deleting Notion page: '{page_title}' (page_id={page_id}, delete_from_kb={delete_from_kb})"
            )

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
                return _emit(
                    {
                        "status": "rejected",
                        "message": "User declined. Do not retry or suggest alternatives.",
                    },
                    status="error",
                    error="user_rejected",
                )

            final_page_id = result.params.get("page_id", page_id)
            final_connector_id = result.params.get(
                "connector_id", connector_id_from_context
            )
            final_delete_from_kb = result.params.get("delete_from_kb", delete_from_kb)

            logger.info(
                f"Deleting Notion page with final params: page_id={final_page_id}, connector_id={final_connector_id}, delete_from_kb={final_delete_from_kb}"
            )

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            # Validate the connector
            if final_connector_id:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == final_connector_id,
                        SearchSourceConnector.workspace_id == workspace_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.NOTION_CONNECTOR,
                    )
                )
                connector = result.scalars().first()

                if not connector:
                    logger.error(
                        f"Invalid connector_id={final_connector_id} for workspace_id={workspace_id}"
                    )
                    return _emit(
                        {
                            "status": "error",
                            "message": "Selected Notion account is invalid or has been disconnected. Please select a valid account.",
                        },
                        status="error",
                        error="invalid_connector",
                    )
                actual_connector_id = connector.id
                logger.info(f"Validated Notion connector: id={actual_connector_id}")
            else:
                logger.error("No connector found for this page")
                return _emit(
                    {
                        "status": "error",
                        "message": "No connector found for this page.",
                    },
                    status="error",
                    error="no_connector",
                )

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

            # If deletion was successful and user wants to delete from KB
            deleted_from_kb = False
            if (
                result.get("status") == "success"
                and final_delete_from_kb
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
                        deleted_from_kb = True
                        logger.info(
                            f"Deleted document {document_id} from knowledge base"
                        )
                    else:
                        logger.warning(f"Document {document_id} not found in KB")
                except Exception as e:
                    logger.error(f"Failed to delete document from KB: {e}")
                    await db_session.rollback()
                    result["warning"] = (
                        f"Page deleted from Notion, but failed to remove from knowledge base: {e!s}"
                    )

            # Update result with KB deletion status
            if result.get("status") == "success":
                result["deleted_from_kb"] = deleted_from_kb
                if deleted_from_kb:
                    result["message"] = (
                        f"{result.get('message', '')} (also removed from knowledge base)"
                    )

            status = result.get("status", "error")
            return _emit(
                result,
                status=status,
                external_id=str(final_page_id) if final_page_id else None,
                error=None if status == "success" else result.get("message"),
            )

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error deleting Notion page: {e}", exc_info=True)
            error_str = str(e).lower()
            if isinstance(e, NotionAPIError) and (
                "401" in error_str or "unauthorized" in error_str
            ):
                return _emit(
                    {
                        "status": "auth_error",
                        "message": str(e),
                        "connector_id": connector_id_from_context
                        if "connector_id_from_context" in dir()
                        else None,
                        "connector_type": "notion",
                    },
                    status="error",
                    error=str(e),
                )
            if isinstance(e, ValueError | NotionAPIError):
                message = str(e)
            else:
                message = (
                    "Something went wrong while deleting the page. Please try again."
                )
            return _emit(
                {"status": "error", "message": message},
                status="error",
                error=message,
            )

    return delete_notion_page
