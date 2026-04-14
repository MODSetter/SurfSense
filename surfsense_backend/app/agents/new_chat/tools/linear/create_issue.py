import logging
from typing import Any

from langchain_core.tools import tool
from app.agents.new_chat.tools.hitl import request_approval
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.linear_connector import LinearAPIError, LinearConnector
from app.services.linear import LinearToolMetadataService

logger = logging.getLogger(__name__)


def create_create_linear_issue_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    """
    Factory function to create the create_linear_issue tool.

    Args:
        db_session: Database session for accessing the Linear connector
        search_space_id: Search space ID to find the Linear connector
        user_id: User ID for fetching user-specific context
        connector_id: Optional specific connector ID (if known)

    Returns:
        Configured create_linear_issue tool
    """

    @tool
    async def create_linear_issue(
        title: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a new issue in Linear.

        Use this tool when the user explicitly asks to create, add, or file
        a new issue / ticket / task in Linear. The user MUST describe the issue
        before you call this tool. If the request is vague, ask what the issue
        should be about. Never call this tool without a clear topic from the user.

        Args:
            title: Short, descriptive issue title. Infer from the user's request.
            description: Optional markdown body for the issue. Generate from context.

        Returns:
            Dictionary with:
            - status: "success", "rejected", or "error"
            - issue_id: Linear issue UUID (if success)
            - identifier: Human-readable ID like "ENG-42" (if success)
            - url: URL to the created issue (if success)
            - message: Result message

            IMPORTANT: If status is "rejected", the user explicitly declined the action.
            Respond with a brief acknowledgment (e.g., "Understood, I won't create the issue.")
            and move on. Do NOT retry, troubleshoot, or suggest alternatives.

        Examples:
            - "Create a Linear issue for the login bug"
            - "File a ticket about the payment timeout problem"
            - "Add an issue for the broken search feature"
        """
        logger.info(f"create_linear_issue called: title='{title}'")

        if db_session is None or search_space_id is None or user_id is None:
            logger.error(
                "Linear tool not properly configured - missing required parameters"
            )
            return {
                "status": "error",
                "message": "Linear tool not properly configured. Please contact support.",
            }

        try:
            metadata_service = LinearToolMetadataService(db_session)
            context = await metadata_service.get_creation_context(
                search_space_id, user_id
            )

            if "error" in context:
                logger.error(f"Failed to fetch creation context: {context['error']}")
                return {"status": "error", "message": context["error"]}

            workspaces = context.get("workspaces", [])
            if workspaces and all(w.get("auth_expired") for w in workspaces):
                logger.warning("All Linear accounts have expired authentication")
                return {
                    "status": "auth_error",
                    "message": "All connected Linear accounts need re-authentication. Please re-authenticate in your connector settings.",
                    "connector_type": "linear",
                }

            logger.info(f"Requesting approval for creating Linear issue: '{title}'")
            result = request_approval(
                action_type="linear_issue_creation",
                tool_name="create_linear_issue",
                params={
                    "title": title,
                    "description": description,
                    "team_id": None,
                    "state_id": None,
                    "assignee_id": None,
                    "priority": None,
                    "label_ids": [],
                    "connector_id": connector_id,
                },
                context=context,
            )

            if result.rejected:
                logger.info("Linear issue creation rejected by user")
                return {
                    "status": "rejected",
                    "message": "User declined. Do not retry or suggest alternatives.",
                }

            final_title = result.params.get("title", title)
            final_description = result.params.get("description", description)
            final_team_id = result.params.get("team_id")
            final_state_id = result.params.get("state_id")
            final_assignee_id = result.params.get("assignee_id")
            final_priority = result.params.get("priority")
            final_label_ids = result.params.get("label_ids") or []
            final_connector_id = result.params.get("connector_id", connector_id)

            if not final_title or not final_title.strip():
                logger.error("Title is empty or contains only whitespace")
                return {"status": "error", "message": "Issue title cannot be empty."}
            if not final_team_id:
                return {
                    "status": "error",
                    "message": "A team must be selected to create an issue.",
                }

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            actual_connector_id = final_connector_id
            if actual_connector_id is None:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.LINEAR_CONNECTOR,
                    )
                )
                connector = result.scalars().first()
                if not connector:
                    return {
                        "status": "error",
                        "message": "No Linear connector found. Please connect Linear in your workspace settings.",
                    }
                actual_connector_id = connector.id
                logger.info(f"Found Linear connector: id={actual_connector_id}")
            else:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == actual_connector_id,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.LINEAR_CONNECTOR,
                    )
                )
                connector = result.scalars().first()
                if not connector:
                    return {
                        "status": "error",
                        "message": "Selected Linear connector is invalid or has been disconnected.",
                    }
                logger.info(f"Validated Linear connector: id={actual_connector_id}")

            logger.info(
                f"Creating Linear issue with final params: title='{final_title}'"
            )
            linear_client = LinearConnector(
                session=db_session, connector_id=actual_connector_id
            )
            result = await linear_client.create_issue(
                team_id=final_team_id,
                title=final_title,
                description=final_description,
                state_id=final_state_id,
                assignee_id=final_assignee_id,
                priority=final_priority,
                label_ids=final_label_ids if final_label_ids else None,
            )

            if result.get("status") == "error":
                logger.error(f"Failed to create Linear issue: {result.get('message')}")
                return {"status": "error", "message": result.get("message")}

            logger.info(
                f"Linear issue created: {result.get('identifier')} - {result.get('title')}"
            )

            kb_message_suffix = ""
            try:
                from app.services.linear import LinearKBSyncService

                kb_service = LinearKBSyncService(db_session)
                kb_result = await kb_service.sync_after_create(
                    issue_id=result.get("id"),
                    issue_identifier=result.get("identifier", ""),
                    issue_title=result.get("title", final_title),
                    issue_url=result.get("url"),
                    description=final_description,
                    connector_id=actual_connector_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                )
                if kb_result["status"] == "success":
                    kb_message_suffix = " Your knowledge base has also been updated."
                else:
                    kb_message_suffix = " This issue will be added to your knowledge base in the next scheduled sync."
            except Exception as kb_err:
                logger.warning(f"KB sync after create failed: {kb_err}")
                kb_message_suffix = " This issue will be added to your knowledge base in the next scheduled sync."

            return {
                "status": "success",
                "issue_id": result.get("id"),
                "identifier": result.get("identifier"),
                "url": result.get("url"),
                "message": (result.get("message", "") + kb_message_suffix),
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error creating Linear issue: {e}", exc_info=True)
            if isinstance(e, ValueError | LinearAPIError):
                message = str(e)
            else:
                message = (
                    "Something went wrong while creating the issue. Please try again."
                )
            return {"status": "error", "message": message}

    return create_linear_issue
