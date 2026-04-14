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


def create_update_jira_issue_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    @tool
    async def update_jira_issue(
        issue_title_or_key: str,
        new_summary: str | None = None,
        new_description: str | None = None,
        new_priority: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing Jira issue.

        Use this tool when the user asks to modify, edit, or update a Jira issue.

        Args:
            issue_title_or_key: The issue key (e.g. "PROJ-42") or title to identify the issue.
            new_summary: Optional new title/summary for the issue.
            new_description: Optional new description.
            new_priority: Optional new priority name.

        Returns:
            Dictionary with status and message.

            IMPORTANT:
            - If status is "rejected", do NOT retry.
            - If status is "not_found", relay the message and ask user to verify.
            - If status is "insufficient_permissions", inform user to re-authenticate.
        """
        logger.info(
            f"update_jira_issue called: issue_title_or_key='{issue_title_or_key}'"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {"status": "error", "message": "Jira tool not properly configured."}

        try:
            metadata_service = JiraToolMetadataService(db_session)
            context = await metadata_service.get_update_context(
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
            document_id = issue_data.get("document_id")
            connector_id_from_context = context.get("account", {}).get("id")

            result = request_approval(
                action_type="jira_issue_update",
                tool_name="update_jira_issue",
                params={
                    "issue_key": issue_key,
                    "document_id": document_id,
                    "new_summary": new_summary,
                    "new_description": new_description,
                    "new_priority": new_priority,
                    "connector_id": connector_id_from_context,
                },
                context=context,
            )

            if result.rejected:
                return {
                    "status": "rejected",
                    "message": "User declined. Do not retry or suggest alternatives.",
                }

            final_issue_key = result.params.get("issue_key", issue_key)
            final_summary = result.params.get("new_summary", new_summary)
            final_description = result.params.get("new_description", new_description)
            final_priority = result.params.get("new_priority", new_priority)
            final_connector_id = result.params.get(
                "connector_id", connector_id_from_context
            )
            final_document_id = result.params.get("document_id", document_id)

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

            fields: dict[str, Any] = {}
            if final_summary:
                fields["summary"] = final_summary
            if final_description is not None:
                fields["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": final_description}],
                        }
                    ],
                }
            if final_priority:
                fields["priority"] = {"name": final_priority}

            if not fields:
                return {"status": "error", "message": "No changes specified."}

            try:
                jira_history = JiraHistoryConnector(
                    session=db_session, connector_id=final_connector_id
                )
                jira_client = await jira_history._get_jira_client()
                await asyncio.to_thread(
                    jira_client.update_issue, final_issue_key, fields
                )
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

            issue_url = (
                f"{jira_history._base_url}/browse/{final_issue_key}"
                if jira_history._base_url and final_issue_key
                else ""
            )

            kb_message_suffix = ""
            if final_document_id:
                try:
                    from app.services.jira import JiraKBSyncService

                    kb_service = JiraKBSyncService(db_session)
                    kb_result = await kb_service.sync_after_update(
                        document_id=final_document_id,
                        issue_id=final_issue_key,
                        user_id=user_id,
                        search_space_id=search_space_id,
                    )
                    if kb_result["status"] == "success":
                        kb_message_suffix = (
                            " Your knowledge base has also been updated."
                        )
                    else:
                        kb_message_suffix = (
                            " The knowledge base will be updated in the next sync."
                        )
                except Exception as kb_err:
                    logger.warning(f"KB sync after update failed: {kb_err}")
                    kb_message_suffix = (
                        " The knowledge base will be updated in the next sync."
                    )

            return {
                "status": "success",
                "issue_key": final_issue_key,
                "issue_url": issue_url,
                "message": f"Jira issue {final_issue_key} updated successfully.{kb_message_suffix}",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error(f"Error updating Jira issue: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while updating the issue.",
            }

    return update_jira_issue
