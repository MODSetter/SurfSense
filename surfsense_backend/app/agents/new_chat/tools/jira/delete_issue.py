import asyncio
import logging
from typing import Any

from langchain_core.tools import tool
from app.agents.new_chat.tools.hitl import request_approval
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.connectors.jira_history import JiraHistoryConnector
from app.services.jira import JiraToolMetadataService

logger = logging.getLogger(__name__)


def create_delete_jira_issue_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    @tool
    async def delete_jira_issue(
        issue_title_or_key: str,
        delete_from_kb: bool = False,
    ) -> dict[str, Any]:
        """Delete a Jira issue.

        Use this tool when the user asks to delete or remove a Jira issue.

        Args:
            issue_title_or_key: The issue key (e.g. "PROJ-42") or title.
            delete_from_kb: Whether to also remove from the knowledge base.

        Returns:
            Dictionary with status, message, and deleted_from_kb.

            IMPORTANT:
            - If status is "rejected", do NOT retry.
            - If status is "not_found", relay the message to the user.
            - If status is "insufficient_permissions", inform user to re-authenticate.
        """
        logger.info(
            f"delete_jira_issue called: issue_title_or_key='{issue_title_or_key}'"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {"status": "error", "message": "Jira tool not properly configured."}

        try:
            metadata_service = JiraToolMetadataService(db_session)
            context = await metadata_service.get_deletion_context(
                search_space_id, user_id, issue_title_or_key
            )

            if "error" in context:
                error_msg = context["error"]
                if context.get("auth_expired"):
                    return {
                        "status": "auth_error",
                        "message": error_msg,
                        "connector_id": context.get("connector_id"),
                        "connector_type": "jira",
                    }
                if "not found" in error_msg.lower():
                    return {"status": "not_found", "message": error_msg}
                return {"status": "error", "message": error_msg}

            issue_data = context["issue"]
            issue_key = issue_data["issue_id"]
            document_id = issue_data["document_id"]
            connector_id_from_context = context.get("account", {}).get("id")

            result = request_approval(
                action_type="jira_issue_deletion",
                tool_name="delete_jira_issue",
                params={
                    "issue_key": issue_key,
                    "connector_id": connector_id_from_context,
                    "delete_from_kb": delete_from_kb,
                },
                context=context,
            )

            if result.rejected:
                return {
                    "status": "rejected",
                    "message": "User declined. Do not retry or suggest alternatives.",
                }

            final_issue_key = result.params.get("issue_key", issue_key)
            final_connector_id = result.params.get(
                "connector_id", connector_id_from_context
            )
            final_delete_from_kb = result.params.get("delete_from_kb", delete_from_kb)

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            if not final_connector_id:
                return {
                    "status": "error",
                    "message": "No connector found for this issue.",
                }

            result = await db_session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == final_connector_id,
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.JIRA_CONNECTOR,
                )
            )
            connector = result.scalars().first()
            if not connector:
                return {
                    "status": "error",
                    "message": "Selected Jira connector is invalid.",
                }

            try:
                jira_history = JiraHistoryConnector(
                    session=db_session, connector_id=final_connector_id
                )
                jira_client = await jira_history._get_jira_client()
                await asyncio.to_thread(jira_client.delete_issue, final_issue_key)
            except Exception as api_err:
                if "status code 403" in str(api_err).lower():
                    try:
                        connector.config = {**connector.config, "auth_expired": True}
                        flag_modified(connector, "config")
                        await db_session.commit()
                    except Exception:
                        pass
                    return {
                        "status": "insufficient_permissions",
                        "connector_id": final_connector_id,
                        "message": "This Jira account needs additional permissions. Please re-authenticate in connector settings.",
                    }
                raise

            deleted_from_kb = False
            if final_delete_from_kb and document_id:
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
                except Exception as e:
                    logger.error(f"Failed to delete document from KB: {e}")
                    await db_session.rollback()

            message = f"Jira issue {final_issue_key} deleted successfully."
            if deleted_from_kb:
                message += " Also removed from the knowledge base."

            return {
                "status": "success",
                "issue_key": final_issue_key,
                "deleted_from_kb": deleted_from_kb,
                "message": message,
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error(f"Error deleting Jira issue: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while deleting the issue.",
            }

    return delete_jira_issue
