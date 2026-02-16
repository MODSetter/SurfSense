import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.notion_history import NotionHistoryConnector
from app.services.notion import NotionToolMetadataService

logger = logging.getLogger(__name__)


def create_update_notion_page_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    """
    Factory function to create the update_notion_page tool.

    Args:
        db_session: Database session for accessing Notion connector
        search_space_id: Search space ID to find the Notion connector
        user_id: User ID for fetching user-specific context
        connector_id: Optional specific connector ID (if known)

    Returns:
        Configured update_notion_page tool
    """

    @tool
    async def update_notion_page(
        page_title: str,
        content: str,
    ) -> dict[str, Any]:
        """Update an existing Notion page by appending new content.

        Use this tool when the user asks you to add content to, modify, or update
        a Notion page. The new content will be appended to the existing page content.

        Args:
            page_title: The title of the Notion page to update.
            content: The markdown content to append to the page body (supports headings, lists, paragraphs).

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
              Example: "I couldn't find the page '[page_title]' in your indexed Notion pages. [message details]"
              Do NOT treat this as an error. Do NOT invent information. Simply relay the message and
              ask the user to verify the page title or check if it's been indexed.

        Examples:
            - "Add 'New meeting notes from today' to the 'Meeting Notes' Notion page"
            - "Append the following to the 'Project Plan' Notion page: '# Status Update\n\nCompleted phase 1'"
        """
        logger.info(
            f"update_notion_page called: page_title='{page_title}', content_length={len(content) if content else 0}"
        )

        if db_session is None or search_space_id is None or user_id is None:
            logger.error(
                "Notion tool not properly configured - missing required parameters"
            )
            return {
                "status": "error",
                "message": "Notion tool not properly configured. Please contact support.",
            }

        if not content or not content.strip():
            logger.error(f"Empty content provided for page '{page_title}'")
            return {
                "status": "error",
                "message": "Content is required to update the page. Please provide the actual content you want to add.",
            }

        try:
            metadata_service = NotionToolMetadataService(db_session)
            context = await metadata_service.get_update_context(
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
                    logger.error(f"Failed to fetch update context: {error_msg}")
                    return {
                        "status": "error",
                        "message": error_msg,
                    }

            page_id = context.get("page_id")
            connector_id_from_context = context.get("account", {}).get("id")

            logger.info(
                f"Requesting approval for updating Notion page: '{page_title}' (page_id={page_id})"
            )
            approval = interrupt(
                {
                    "type": "notion_page_update",
                    "action": {
                        "tool": "update_notion_page",
                        "params": {
                            "page_id": page_id,
                            "content": content,
                            "connector_id": connector_id_from_context,
                        },
                    },
                    "context": context,
                }
            )

            decisions_raw = approval.get("decisions", []) if isinstance(approval, dict) else []
            decisions = decisions_raw if isinstance(decisions_raw, list) else [decisions_raw]
            decisions = [d for d in decisions if isinstance(d, dict)]
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
                logger.info("Notion page update rejected by user")
                return {
                    "status": "rejected",
                    "message": "User declined. The page was not updated. Do not ask again or suggest alternatives.",
                }

            edited_action = decision.get("edited_action")
            final_params: dict[str, Any] = {}
            if isinstance(edited_action, dict):
                edited_args = edited_action.get("args")
                if isinstance(edited_args, dict):
                    final_params = edited_args
            elif isinstance(decision.get("args"), dict):
                # Some interrupt payloads place args directly on the decision.
                final_params = decision["args"]

            final_page_id = final_params.get("page_id", page_id)
            final_content = final_params.get("content", content)
            final_connector_id = final_params.get(
                "connector_id", connector_id_from_context
            )

            logger.info(
                f"Updating Notion page with final params: page_id={final_page_id}, has_content={final_content is not None}"
            )

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

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

            notion_connector = NotionHistoryConnector(
                session=db_session,
                connector_id=actual_connector_id,
            )

            result = await notion_connector.update_page(
                page_id=final_page_id,
                content=final_content,
            )
            logger.info(
                f"update_page result: {result.get('status')} - {result.get('message', '')}"
            )
            return result

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error updating Notion page: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
                if isinstance(e, ValueError)
                else f"Unexpected error: {e!s}",
            }

    return update_notion_page
