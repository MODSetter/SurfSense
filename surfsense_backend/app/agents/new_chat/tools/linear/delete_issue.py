import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.linear_connector import LinearConnector
from app.services.linear import LinearToolMetadataService

logger = logging.getLogger(__name__)


def create_delete_linear_issue_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    """
    Factory function to create the delete_linear_issue tool.

    Args:
        db_session: Database session for accessing the Linear connector
        search_space_id: Search space ID to find the Linear connector
        user_id: User ID for finding the correct Linear connector
        connector_id: Optional specific connector ID (if known)

    Returns:
        Configured delete_linear_issue tool
    """

    @tool
    async def delete_linear_issue(
        issue_ref: str,
        delete_from_kb: bool = False,
    ) -> dict[str, Any]:
        """Archive (delete) a Linear issue.

        Use this tool when the user asks to delete, remove, or archive a Linear issue.
        Note that Linear archives issues rather than permanently deleting them
        (they can be restored from the archive).


        Args:
            issue_ref: The issue to delete. Can be the issue title (e.g. "Fix login bug"),
                       the identifier (e.g. "ENG-42"), or the full document title
                       (e.g. "ENG-42: Fix login bug").
            delete_from_kb: Whether to also remove the issue from the knowledge base.
                            Default is False. Set to True to remove from both Linear
                            and the knowledge base.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "not_found", or "error"
            - identifier: Human-readable ID like "ENG-42" (if success)
            - message: Success or error message
            - deleted_from_kb: Whether the issue was also removed from the knowledge base (if success)

            IMPORTANT:
            - If status is "rejected", the user explicitly declined the action.
              Respond with a brief acknowledgment (e.g., "Understood, I won't delete the issue.")
              and move on. Do NOT ask for alternatives or troubleshoot.
            - If status is "not_found", inform the user conversationally using the exact message
              provided. Do NOT treat this as an error. Simply relay the message and ask the user
              to verify the issue title or identifier, or check if it has been indexed.

        Examples:
            - "Delete the 'Fix login bug' Linear issue"
            - "Archive ENG-42"
            - "Remove the 'Old payment flow' issue from Linear"
        """
        logger.info(
            f"delete_linear_issue called: issue_ref='{issue_ref}', delete_from_kb={delete_from_kb}"
        )

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
            context = await metadata_service.get_delete_context(
                search_space_id, user_id, issue_ref
            )

            if "error" in context:
                error_msg = context["error"]
                if "not found" in error_msg.lower():
                    logger.warning(f"Issue not found: {error_msg}")
                    return {"status": "not_found", "message": error_msg}
                else:
                    logger.error(f"Failed to fetch delete context: {error_msg}")
                    return {"status": "error", "message": error_msg}

            issue_id = context["issue"]["id"]
            issue_identifier = context["issue"].get("identifier", "")
            document_id = context["issue"]["document_id"]
            connector_id_from_context = context.get("workspace", {}).get("id")

            logger.info(
                f"Requesting approval for deleting Linear issue: '{issue_ref}' "
                f"(id={issue_id}, delete_from_kb={delete_from_kb})"
            )
            approval = interrupt(
                {
                    "type": "linear_issue_deletion",
                    "action": {
                        "tool": "delete_linear_issue",
                        "params": {
                            "issue_id": issue_id,
                            "connector_id": connector_id_from_context,
                            "delete_from_kb": delete_from_kb,
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
                logger.info("Linear issue deletion rejected by user")
                return {
                    "status": "rejected",
                    "message": "User declined. The issue was not deleted. Do not ask again or suggest alternatives.",
                }

            edited_action = decision.get("edited_action")
            final_params: dict[str, Any] = {}
            if isinstance(edited_action, dict):
                edited_args = edited_action.get("args")
                if isinstance(edited_args, dict):
                    final_params = edited_args
            elif isinstance(decision.get("args"), dict):
                final_params = decision["args"]

            final_issue_id = final_params.get("issue_id", issue_id)
            final_connector_id = final_params.get(
                "connector_id", connector_id_from_context
            )
            final_delete_from_kb = final_params.get("delete_from_kb", delete_from_kb)

            logger.info(
                f"Deleting Linear issue with final params: issue_id={final_issue_id}, "
                f"connector_id={final_connector_id}, delete_from_kb={final_delete_from_kb}"
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
                actual_connector_id = connector.id
                logger.info(f"Validated Linear connector: id={actual_connector_id}")
            else:
                logger.error("No connector found for this issue")
                return {
                    "status": "error",
                    "message": "No connector found for this issue.",
                }

            linear_client = LinearConnector(
                session=db_session, connector_id=actual_connector_id
            )

            result = await linear_client.archive_issue(issue_id=final_issue_id)

            logger.info(
                f"archive_issue result: {result.get('status')} - {result.get('message', '')}"
            )

            deleted_from_kb = False
            if (
                result.get("status") == "success"
                and final_delete_from_kb
                and document_id
            ):
                try:
                    from app.db import Document

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
                        f"Issue archived in Linear, but failed to remove from knowledge base: {e!s}"
                    )

            if result.get("status") == "success":
                result["deleted_from_kb"] = deleted_from_kb
                if issue_identifier:
                    result["message"] = f"Issue {issue_identifier} archived successfully."
                if deleted_from_kb:
                    result["message"] = (
                        f"{result.get('message', '')} Also removed from the knowledge base."
                    )

            return result

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error deleting Linear issue: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
                if isinstance(e, ValueError)
                else f"Unexpected error: {e!s}",
            }

    return delete_linear_issue
