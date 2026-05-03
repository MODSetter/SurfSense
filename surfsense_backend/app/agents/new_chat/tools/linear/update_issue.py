import logging
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.hitl import request_approval
from app.connectors.linear_connector import LinearAPIError, LinearConnector
from app.db import async_session_maker
from app.services.linear import LinearKBSyncService, LinearToolMetadataService

logger = logging.getLogger(__name__)


def create_update_linear_issue_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    """Factory function to create the update_linear_issue tool.

    The tool acquires its own short-lived ``AsyncSession`` per call via
    :data:`async_session_maker`. This is critical for the compiled-agent
    cache: the compiled graph (and therefore this closure) is reused
    across HTTP requests, so capturing a per-request session here would
    surface stale/closed sessions on cache hits.

    Args:
        db_session: Reserved for registry compatibility. Per-call sessions
            are opened via :data:`async_session_maker` inside the tool body.
        search_space_id: Search space ID to find the Linear connector
        user_id: User ID for fetching user-specific context
        connector_id: Optional specific connector ID (if known)

    Returns:
        Configured update_linear_issue tool
    """
    del db_session  # per-call session — see docstring

    @tool
    async def update_linear_issue(
        issue_ref: str,
        new_title: str | None = None,
        new_description: str | None = None,
        new_state_name: str | None = None,
        new_assignee_email: str | None = None,
        new_priority: int | None = None,
        new_label_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing Linear issue that has been indexed in the knowledge base.

        Use this tool when the user asks to modify, change, or update a Linear issue —
        for example, changing its status, reassigning it, updating its title or description,
        adjusting its priority, or changing its labels.

        Only issues already indexed in the knowledge base can be updated.

        Args:
            issue_ref: The issue to update. Can be the issue title (e.g. "Fix login bug"),
                       the identifier (e.g. "ENG-42"), or the full document title
                       (e.g. "ENG-42: Fix login bug"). Matched case-insensitively.
            new_title: New title for the issue (optional).
            new_description: New markdown body for the issue (optional).
            new_state_name: New workflow state name (e.g. "In Progress", "Done").
                            Matched case-insensitively against the team's states.
            new_assignee_email: Email address of the new assignee.
                                Matched case-insensitively against the team's members.
            new_priority: New priority (0 = No Priority, 1 = Urgent, 2 = High,
                          3 = Medium, 4 = Low).
            new_label_names: New set of label names to apply.
                             Matched case-insensitively against the team's labels.
                             Unrecognised names are silently skipped.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "not_found", or "error"
            - identifier: Human-readable ID like "ENG-42" (if success)
            - url: URL to the updated issue (if success)
            - message: Result message

            IMPORTANT:
            - If status is "rejected", the user explicitly declined the action.
              Respond with a brief acknowledgment (e.g., "Understood, I didn't update the issue.")
              and move on. Do NOT ask for alternatives or troubleshoot.
            - If status is "not_found", inform the user conversationally using the exact message
              provided. Do NOT treat this as an error. Simply relay the message and ask the user
              to verify the issue title or identifier, or check if it has been indexed.

        Examples:
            - "Mark the 'Fix login bug' issue as done"
            - "Assign ENG-42 to john@company.com"
            - "Change the priority of 'Payment timeout' to urgent"
        """
        logger.info(f"update_linear_issue called: issue_ref='{issue_ref}'")

        if search_space_id is None or user_id is None:
            logger.error(
                "Linear tool not properly configured - missing required parameters"
            )
            return {
                "status": "error",
                "message": "Linear tool not properly configured. Please contact support.",
            }

        try:
            async with async_session_maker() as db_session:
                metadata_service = LinearToolMetadataService(db_session)
                context = await metadata_service.get_update_context(
                    search_space_id, user_id, issue_ref
                )

                if "error" in context:
                    error_msg = context["error"]
                    if context.get("auth_expired"):
                        logger.warning(f"Auth expired for update context: {error_msg}")
                        return {
                            "status": "auth_error",
                            "message": error_msg,
                            "connector_id": context.get("connector_id"),
                            "connector_type": "linear",
                        }
                    if "not found" in error_msg.lower():
                        logger.warning(f"Issue not found: {error_msg}")
                        return {"status": "not_found", "message": error_msg}
                    else:
                        logger.error(f"Failed to fetch update context: {error_msg}")
                        return {"status": "error", "message": error_msg}

                issue_id = context["issue"]["id"]
                document_id = context["issue"]["document_id"]
                connector_id_from_context = context.get("workspace", {}).get("id")

                team = context.get("team", {})
                new_state_id = _resolve_state(team, new_state_name)
                new_assignee_id = _resolve_assignee(team, new_assignee_email)
                new_label_ids = _resolve_labels(team, new_label_names)

                logger.info(
                    f"Requesting approval for updating Linear issue: '{issue_ref}' (id={issue_id})"
                )
                result = request_approval(
                    action_type="linear_issue_update",
                    tool_name="update_linear_issue",
                    params={
                        "issue_id": issue_id,
                        "document_id": document_id,
                        "new_title": new_title,
                        "new_description": new_description,
                        "new_state_id": new_state_id,
                        "new_assignee_id": new_assignee_id,
                        "new_priority": new_priority,
                        "new_label_ids": new_label_ids,
                        "connector_id": connector_id_from_context,
                    },
                    context=context,
                )

                if result.rejected:
                    logger.info("Linear issue update rejected by user")
                    return {
                        "status": "rejected",
                        "message": "User declined. Do not retry or suggest alternatives.",
                    }

                final_issue_id = result.params.get("issue_id", issue_id)
                final_document_id = result.params.get("document_id", document_id)
                final_new_title = result.params.get("new_title", new_title)
                final_new_description = result.params.get(
                    "new_description", new_description
                )
                final_new_state_id = result.params.get("new_state_id", new_state_id)
                final_new_assignee_id = result.params.get(
                    "new_assignee_id", new_assignee_id
                )
                final_new_priority = result.params.get("new_priority", new_priority)
                final_new_label_ids: list[str] | None = result.params.get(
                    "new_label_ids", new_label_ids
                )
                final_connector_id = result.params.get(
                    "connector_id", connector_id_from_context
                )

                if not final_connector_id:
                    logger.error("No connector found for this issue")
                    return {
                        "status": "error",
                        "message": "No connector found for this issue.",
                    }

                from sqlalchemy.future import select

                from app.db import SearchSourceConnector, SearchSourceConnectorType

                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == final_connector_id,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.LINEAR_CONNECTOR,
                    )
                )
                connector = result.scalars().first()
                if not connector:
                    logger.error(
                        f"Invalid connector_id={final_connector_id} for search_space_id={search_space_id}"
                    )
                    return {
                        "status": "error",
                        "message": "Selected Linear connector is invalid or has been disconnected.",
                    }
                logger.info(f"Validated Linear connector: id={final_connector_id}")

                logger.info(
                    f"Updating Linear issue with final params: issue_id={final_issue_id}"
                )
                linear_client = LinearConnector(
                    session=db_session, connector_id=final_connector_id
                )
                updated_issue = await linear_client.update_issue(
                    issue_id=final_issue_id,
                    title=final_new_title,
                    description=final_new_description,
                    state_id=final_new_state_id,
                    assignee_id=final_new_assignee_id,
                    priority=final_new_priority,
                    label_ids=final_new_label_ids,
                )

                if updated_issue.get("status") == "error":
                    logger.error(
                        f"Failed to update Linear issue: {updated_issue.get('message')}"
                    )
                    return {
                        "status": "error",
                        "message": updated_issue.get("message"),
                    }

                logger.info(
                    f"update_issue result: {updated_issue.get('identifier')} - {updated_issue.get('title')}"
                )

                if final_document_id is not None:
                    logger.info(
                        f"Updating knowledge base for document {final_document_id}..."
                    )
                    kb_service = LinearKBSyncService(db_session)
                    kb_result = await kb_service.sync_after_update(
                        document_id=final_document_id,
                        issue_id=final_issue_id,
                        user_id=user_id,
                        search_space_id=search_space_id,
                    )
                    if kb_result["status"] == "success":
                        logger.info(
                            f"Knowledge base successfully updated for issue {final_issue_id}"
                        )
                        kb_message = " Your knowledge base has also been updated."
                    elif kb_result["status"] == "not_indexed":
                        kb_message = " This issue will be added to your knowledge base in the next scheduled sync."
                    else:
                        logger.warning(
                            f"KB update failed for issue {final_issue_id}: {kb_result.get('message')}"
                        )
                        kb_message = " Your knowledge base will be updated in the next scheduled sync."
                else:
                    kb_message = ""

                identifier = updated_issue.get("identifier")
                default_msg = f"Issue {identifier} updated successfully."
                return {
                    "status": "success",
                    "identifier": identifier,
                    "url": updated_issue.get("url"),
                    "message": f"{updated_issue.get('message', default_msg)}{kb_message}",
                }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error updating Linear issue: {e}", exc_info=True)
            if isinstance(e, ValueError | LinearAPIError):
                message = str(e)
            else:
                message = (
                    "Something went wrong while updating the issue. Please try again."
                )
            return {"status": "error", "message": message}

    return update_linear_issue


def _resolve_state(team: dict, state_name: str | None) -> str | None:
    if not state_name:
        return None
    name_lower = state_name.lower()
    for state in team.get("states", []):
        if state.get("name", "").lower() == name_lower:
            return state["id"]
    return None


def _resolve_assignee(team: dict, assignee_email: str | None) -> str | None:
    if not assignee_email:
        return None
    email_lower = assignee_email.lower()
    for member in team.get("members", []):
        if member.get("email", "").lower() == email_lower:
            return member["id"]
    return None


def _resolve_labels(team: dict, label_names: list[str] | None) -> list[str] | None:
    if label_names is None:
        return None
    if not label_names:
        return []
    name_set = {n.lower() for n in label_names}
    return [
        label["id"]
        for label in team.get("labels", [])
        if label.get("name", "").lower() in name_set
    ]
