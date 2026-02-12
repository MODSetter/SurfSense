from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.notion_history import NotionHistoryConnector
from app.services.notion import NotionToolMetadataService


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
        page_id: str,
        title: str | None = None,
        content: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing Notion page's title and/or content.

        Use this tool when the user asks you to modify, edit, or update
        a Notion page. At least one of title or content must be provided.

        Args:
            page_id: The ID of the Notion page to update (required).
            title: New title for the page (optional).
            content: New markdown content for the page body (optional).
                    If provided, replaces all existing content.

        Returns:
            Dictionary with:
            - status: "success", "rejected", or "error"
            - page_id: Updated page ID (if success)
            - url: URL to the updated page (if success)
            - title: Current page title (if success)
            - message: Result message

            IMPORTANT: If status is "rejected", the user explicitly declined the action.
            Respond with a brief acknowledgment (e.g., "Understood, I didn't update the page.")
            and move on. Do NOT ask for alternatives or troubleshoot.

        Examples:
            - "Update the Notion page abc123 with title 'Updated Meeting Notes'"
            - "Change the content of page xyz789 to 'New content here'"
            - "Update page abc123 with new title 'Final Report' and content '# Summary...'"
        """
        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Notion tool not properly configured. Please contact support.",
            }

        if not title and not content:
            return {
                "status": "error",
                "message": "At least one of 'title' or 'content' must be provided to update the page.",
            }

        try:
            metadata_service = NotionToolMetadataService(db_session)
            context = await metadata_service.get_update_context(
                search_space_id, user_id, page_id
            )

            if "error" in context:
                return {
                    "status": "error",
                    "message": context["error"],
                }

            approval = interrupt({
                "type": "notion_page_update",
                "action": {
                    "tool": "update_notion_page",
                    "params": {
                        "page_id": page_id,
                        "title": title,
                        "content": content,
                    },
                },
                "context": context,
            })

            decisions = approval.get("decisions", [])
            if not decisions:
                return {
                    "status": "error",
                    "message": "No approval decision received",
                }

            decision = decisions[0]
            decision_type = decision.get("type") or decision.get("decision_type")

            if decision_type == "reject":
                return {
                    "status": "rejected",
                    "message": "User declined. The page was not updated. Do not ask again or suggest alternatives.",
                }

            edited_action = decision.get("edited_action", {})
            final_params = edited_action.get("args", {}) if edited_action else {}

            final_page_id = final_params.get("page_id", page_id)
            final_title = final_params.get("title", title)
            final_content = final_params.get("content", content)

            if final_title and (not final_title or not final_title.strip()):
                return {
                    "status": "error",
                    "message": "Page title cannot be empty. Please provide a valid title.",
                }

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            connector_id_from_context = context.get("account", {}).get("id")
            
            if connector_id_from_context:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == connector_id_from_context,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.NOTION_CONNECTOR,
                    )
                )
                connector = result.scalars().first()

                if not connector:
                    return {
                        "status": "error",
                        "message": "Selected Notion account is invalid or has been disconnected. Please select a valid account.",
                    }
                actual_connector_id = connector.id
            else:
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
                title=final_title,
                content=final_content,
            )
            return result

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            return {
                "status": "error",
                "message": str(e) if isinstance(e, ValueError) else f"Unexpected error: {e!s}",
            }

    return update_notion_page
