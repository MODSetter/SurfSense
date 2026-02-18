import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.linear_connector import LinearConnector
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
        a new issue / ticket / task in Linear.

        Args:
            title: Short, descriptive issue title.
            description: Optional markdown body for the issue.

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
            - "Create a Linear issue titled 'Fix login bug'"
            - "Add a ticket for the payment timeout problem"
            - "File an issue about the broken search feature"
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

            logger.info(f"Requesting approval for creating Linear issue: '{title}'")
            approval = interrupt(
                {
                    "type": "linear_issue_creation",
                    "action": {
                        "tool": "create_linear_issue",
                        "params": {
                            "title": title,
                            "description": description,
                            "team_id": None,
                            "state_id": None,
                            "assignee_id": None,
                            "priority": None,
                            "label_ids": [],
                            "connector_id": connector_id,
                        },
                    },
                    "context": context,
                }
            )

            decisions_raw = (
                approval.get("decisions", []) if isinstance(approval, dict) else []
            )
            decisions = (
                decisions_raw if isinstance(decisions_raw, list) else [decisions_raw]
            )
            decisions = [d for d in decisions if isinstance(d, dict)]
            if not decisions:
                logger.warning("No approval decision received")
                return {"status": "error", "message": "No approval decision received"}

            decision = decisions[0]
            decision_type = decision.get("type") or decision.get("decision_type")
            logger.info(f"User decision: {decision_type}")

            if decision_type == "reject":
                logger.info("Linear issue creation rejected by user")
                return {
                    "status": "rejected",
                    "message": "User declined. The issue was not created. Do not ask again or suggest alternatives.",
                }

            final_params: dict[str, Any] = {}
            edited_action = decision.get("edited_action")
            if isinstance(edited_action, dict):
                edited_args = edited_action.get("args")
                if isinstance(edited_args, dict):
                    final_params = edited_args
            elif isinstance(decision.get("args"), dict):
                final_params = decision["args"]

            final_title = final_params.get("title", title)
            final_description = final_params.get("description", description)
            final_team_id = final_params.get("team_id")
            final_state_id = final_params.get("state_id")
            final_assignee_id = final_params.get("assignee_id")
            final_priority = final_params.get("priority")
            final_label_ids = final_params.get("label_ids") or []
            final_connector_id = final_params.get("connector_id", connector_id)

            if not final_title or not final_title.strip():
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
            issue = await linear_client.create_issue(
                team_id=final_team_id,
                title=final_title,
                description=final_description,
                state_id=final_state_id,
                assignee_id=final_assignee_id,
                priority=final_priority,
                label_ids=final_label_ids if final_label_ids else None,
            )

            logger.info(
                f"Linear issue created: {issue.get('identifier')} - {issue.get('title')}"
            )
            return {
                "status": "success",
                "issue_id": issue.get("id"),
                "identifier": issue.get("identifier"),
                "url": issue.get("url"),
                "message": f"Issue {issue.get('identifier')} created successfully.",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error creating Linear issue: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
                if isinstance(e, ValueError)
                else f"Unexpected error: {e!s}",
            }

    return create_linear_issue
