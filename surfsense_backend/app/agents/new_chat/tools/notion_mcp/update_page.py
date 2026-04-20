import logging
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.hitl import request_approval
from app.services.notion import NotionToolMetadataService

logger = logging.getLogger(__name__)


def create_update_notion_page_mcp_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    @tool
    async def update_notion_page(
        page_title: str,
        content: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing Notion page by appending new content.

        Use this tool when the user asks you to add content to, modify, or update
        a Notion page. The new content will be appended to the existing page content.
        The user MUST specify what to add before you call this tool. If the
        request is vague, ask what content they want added.

        Args:
            page_title: The title of the Notion page to update.
            content: Optional markdown content to append to the page body (supports headings, lists, paragraphs).
                     Generate this yourself based on the user's request.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "not_found", or "error"
            - page_id: Updated page ID (if success)
            - url: URL to the updated page (if success)
            - title: Current page title (if success)
            - message: Result message

            IMPORTANT:
            - If status is "rejected", the user explicitly declined the action.
              Respond with a brief acknowledgment (e.g., "Understood, I didn't update the page.")
              and move on. Do NOT ask for alternatives or troubleshoot.
            - If status is "not_found", inform the user conversationally using the exact message provided.

        Examples:
            - "Add today's meeting notes to the 'Meeting Notes' Notion page"
            - "Update the 'Project Plan' page with a status update on phase 1"
        """
        logger.info(
            "update_notion_page (MCP) called: page_title='%s', content_length=%d",
            page_title,
            len(content) if content else 0,
        )

        if db_session is None or search_space_id is None or user_id is None:
            logger.error("Notion MCP tool not properly configured - missing required parameters")
            return {
                "status": "error",
                "message": "Notion tool not properly configured. Please contact support.",
            }

        if not content or not content.strip():
            return {
                "status": "error",
                "message": "Content is required to update the page. Please provide the actual content you want to add.",
            }

        try:
            metadata_service = NotionToolMetadataService(db_session)
            context = await metadata_service.get_update_context(search_space_id, user_id, page_title)

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
            document_id = context.get("document_id")
            connector_id_from_context = account.get("id")

            result = request_approval(
                action_type="notion_page_update",
                tool_name="update_notion_page",
                params={
                    "page_id": page_id,
                    "content": content,
                    "connector_id": connector_id_from_context,
                },
                context=context,
            )

            if result.rejected:
                logger.info("Notion page update rejected by user")
                return {
                    "status": "rejected",
                    "message": "User declined. Do not retry or suggest alternatives.",
                }

            final_page_id = result.params.get("page_id", page_id)
            final_content = result.params.get("content", content)
            final_connector_id = result.params.get("connector_id", connector_id_from_context)

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
            result = await adapter.update_page(page_id=final_page_id, content=final_content)
            logger.info("update_page (MCP) result: %s - %s", result.get("status"), result.get("message", ""))

            if result.get("status") == "success" and document_id is not None:
                from app.services.notion import NotionKBSyncService

                kb_service = NotionKBSyncService(db_session)
                kb_result = await kb_service.sync_after_update(
                    document_id=document_id,
                    appended_content=final_content,
                    user_id=user_id,
                    search_space_id=search_space_id,
                    appended_block_ids=result.get("appended_block_ids"),
                )

                if kb_result["status"] == "success":
                    result["message"] = f"{result['message']}. Your knowledge base has also been updated."
                elif kb_result["status"] == "not_indexed":
                    result["message"] = f"{result['message']}. This page will be added to your knowledge base in the next scheduled sync."
                else:
                    result["message"] = f"{result['message']}. Your knowledge base will be updated in the next scheduled sync."

            return result

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error("Error updating Notion page (MCP): %s", e, exc_info=True)
            if isinstance(e, ValueError):
                message = str(e)
            else:
                message = "Something went wrong while updating the page. Please try again."
            return {"status": "error", "message": message}

    return update_notion_page
