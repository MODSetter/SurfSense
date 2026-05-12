import logging
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.hitl import request_approval
from app.connectors.notion_history import NotionAPIError, NotionHistoryConnector
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
        content: str | None = None,
    ) -> dict[str, Any]:
        """Create a new page in Notion with the given title and content.

        Use this tool when the user asks you to create, save, or publish
        something to Notion. The page will be created in the user's
        configured Notion workspace. The user MUST specify a topic before you
        call this tool. If the request does not contain a topic (e.g. "create a
        notion page"), ask what the page should be about. Never call this tool
        without a clear topic from the user.

        Args:
            title: The title of the Notion page.
            content: Optional markdown content for the page body (supports headings, lists, paragraphs).
                     Generate this yourself based on the user's topic.

        Returns:
            Dictionary with:
            - status: "success", "rejected", or "error"
            - page_id: Created page ID (if success)
            - url: URL to the created page (if success)
            - title: Page title (if success)
            - message: Result message

            IMPORTANT: If status is "rejected", the user explicitly declined the action.
            Respond with a brief acknowledgment (e.g., "Understood, I didn't create the page.")
            and move on. Do NOT troubleshoot or suggest alternatives.

        Examples:
            - "Create a Notion page about our Q2 roadmap"
            - "Save a summary of today's discussion to Notion"
        """
        logger.info(f"create_notion_page called: title='{title}'")

        if db_session is None or search_space_id is None or user_id is None:
            logger.error(
                "Notion tool not properly configured - missing required parameters"
            )
            return {
                "status": "error",
                "message": "Notion tool not properly configured. Please contact support.",
            }

        try:
            metadata_service = NotionToolMetadataService(db_session)
            context = await metadata_service.get_creation_context(
                search_space_id, user_id
            )

            if "error" in context:
                logger.error(f"Failed to fetch creation context: {context['error']}")
                return {
                    "status": "error",
                    "message": context["error"],
                }

            accounts = context.get("accounts", [])
            if accounts and all(a.get("auth_expired") for a in accounts):
                logger.warning("All Notion accounts have expired authentication")
                return {
                    "status": "auth_error",
                    "message": "All connected Notion accounts need re-authentication. Please re-authenticate in your connector settings.",
                    "connector_type": "notion",
                }

            logger.info(f"Requesting approval for creating Notion page: '{title}'")
            result = request_approval(
                action_type="notion_page_creation",
                tool_name="create_notion_page",
                params={
                    "title": title,
                    "content": content,
                    "parent_page_id": None,
                    "connector_id": connector_id,
                },
                context=context,
            )

            if result.rejected:
                logger.info("Notion page creation rejected by user")
                return {
                    "status": "rejected",
                    "message": "User declined. Do not retry or suggest alternatives.",
                }

            final_title = result.params.get("title", title)
            final_content = result.params.get("content", content)
            final_parent_page_id = result.params.get("parent_page_id")
            final_connector_id = result.params.get("connector_id", connector_id)

            if not final_title or not final_title.strip():
                logger.error("Title is empty or contains only whitespace")
                return {
                    "status": "error",
                    "message": "Page title cannot be empty. Please provide a valid title.",
                }

            logger.info(
                f"Creating Notion page with final params: title='{final_title}'"
            )

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
                    logger.warning(
                        f"No Notion connector found for search_space_id={search_space_id}"
                    )
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
            logger.info(
                f"create_page result: {result.get('status')} - {result.get('message', '')}"
            )

            if result.get("status") == "success":
                kb_message_suffix = ""
                try:
                    from app.services.notion import NotionKBSyncService

                    kb_service = NotionKBSyncService(db_session)
                    kb_result = await kb_service.sync_after_create(
                        page_id=result.get("page_id"),
                        page_title=result.get("title", final_title),
                        page_url=result.get("url"),
                        content=final_content,
                        connector_id=actual_connector_id,
                        search_space_id=search_space_id,
                        user_id=user_id,
                    )
                    if kb_result["status"] == "success":
                        kb_message_suffix = (
                            " Your knowledge base has also been updated."
                        )
                    else:
                        kb_message_suffix = " This page will be added to your knowledge base in the next scheduled sync."
                except Exception as kb_err:
                    logger.warning(f"KB sync after create failed: {kb_err}")
                    kb_message_suffix = " This page will be added to your knowledge base in the next scheduled sync."

                result["message"] = result.get("message", "") + kb_message_suffix

            return result

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error creating Notion page: {e}", exc_info=True)
            if isinstance(e, ValueError | NotionAPIError):
                message = str(e)
            else:
                message = (
                    "Something went wrong while creating the page. Please try again."
                )
            return {"status": "error", "message": message}

    return create_notion_page
