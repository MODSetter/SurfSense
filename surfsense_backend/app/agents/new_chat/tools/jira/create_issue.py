import asyncio
import logging
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.agents.new_chat.tools.hitl import request_approval
from app.connectors.jira_history import JiraHistoryConnector
from app.db import async_session_maker
from app.services.jira import JiraToolMetadataService

logger = logging.getLogger(__name__)


def create_create_jira_issue_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
    """Factory function to create the create_jira_issue tool.

    The tool acquires its own short-lived ``AsyncSession`` per call via
    :data:`async_session_maker`. This is critical for the compiled-agent
    cache: the compiled graph (and therefore this closure) is reused
    across HTTP requests, so capturing a per-request session here would
    surface stale/closed sessions on cache hits. Per-call sessions also
    keep the request's outer transaction free of long-running Jira API
    blocking.

    Args:
        db_session: Reserved for registry compatibility. Per-call sessions
            are opened via :data:`async_session_maker` inside the tool body.
        search_space_id: Search space ID to find the Jira connector
        user_id: User ID for fetching user-specific context
        connector_id: Optional specific connector ID (if known)

    Returns:
        Configured create_jira_issue tool
    """
    del db_session  # per-call session — see docstring

    @tool
    async def create_jira_issue(
        project_key: str,
        summary: str,
        issue_type: str = "Task",
        description: str | None = None,
        priority: str | None = None,
    ) -> dict[str, Any]:
        """Create a new issue in Jira.

        Use this tool when the user explicitly asks to create a new Jira issue/ticket.

        Args:
            project_key: The Jira project key (e.g. "PROJ", "ENG").
            summary: Short, descriptive issue title.
            issue_type: Issue type (default "Task"). Others: "Bug", "Story", "Epic".
            description: Optional description body for the issue.
            priority: Optional priority name (e.g. "High", "Medium", "Low").

        Returns:
            Dictionary with status, issue_key, and message.

            IMPORTANT:
            - If status is "rejected", the user declined. Do NOT retry.
            - If status is "insufficient_permissions", inform user to re-authenticate.
        """
        logger.info(
            f"create_jira_issue called: project_key='{project_key}', summary='{summary}'"
        )

        if search_space_id is None or user_id is None:
            return {"status": "error", "message": "Jira tool not properly configured."}

        try:
            async with async_session_maker() as db_session:
                metadata_service = JiraToolMetadataService(db_session)
                context = await metadata_service.get_creation_context(
                    search_space_id, user_id
                )

                if "error" in context:
                    return {"status": "error", "message": context["error"]}

                accounts = context.get("accounts", [])
                if accounts and all(a.get("auth_expired") for a in accounts):
                    return {
                        "status": "auth_error",
                        "message": "All connected Jira accounts need re-authentication.",
                        "connector_type": "jira",
                    }

                result = request_approval(
                    action_type="jira_issue_creation",
                    tool_name="create_jira_issue",
                    params={
                        "project_key": project_key,
                        "summary": summary,
                        "issue_type": issue_type,
                        "description": description,
                        "priority": priority,
                        "connector_id": connector_id,
                    },
                    context=context,
                )

                if result.rejected:
                    return {
                        "status": "rejected",
                        "message": "User declined. Do not retry or suggest alternatives.",
                    }

                final_project_key = result.params.get("project_key", project_key)
                final_summary = result.params.get("summary", summary)
                final_issue_type = result.params.get("issue_type", issue_type)
                final_description = result.params.get("description", description)
                final_priority = result.params.get("priority", priority)
                final_connector_id = result.params.get("connector_id", connector_id)

                if not final_summary or not final_summary.strip():
                    return {
                        "status": "error",
                        "message": "Issue summary cannot be empty.",
                    }
                if not final_project_key:
                    return {"status": "error", "message": "A project must be selected."}

                from sqlalchemy.future import select

                from app.db import SearchSourceConnector, SearchSourceConnectorType

                actual_connector_id = final_connector_id
                if actual_connector_id is None:
                    result = await db_session.execute(
                        select(SearchSourceConnector).filter(
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
                            "message": "No Jira connector found.",
                        }
                    actual_connector_id = connector.id
                else:
                    result = await db_session.execute(
                        select(SearchSourceConnector).filter(
                            SearchSourceConnector.id == actual_connector_id,
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
                        session=db_session, connector_id=actual_connector_id
                    )
                    jira_client = await jira_history._get_jira_client()
                    api_result = await asyncio.to_thread(
                        jira_client.create_issue,
                        project_key=final_project_key,
                        summary=final_summary,
                        issue_type=final_issue_type,
                        description=final_description,
                        priority=final_priority,
                    )
                except Exception as api_err:
                    if "status code 403" in str(api_err).lower():
                        try:
                            _conn = connector
                            _conn.config = {**_conn.config, "auth_expired": True}
                            flag_modified(_conn, "config")
                            await db_session.commit()
                        except Exception:
                            pass
                        return {
                            "status": "insufficient_permissions",
                            "connector_id": actual_connector_id,
                            "message": "This Jira account needs additional permissions. Please re-authenticate in connector settings.",
                        }
                    raise

                issue_key = api_result.get("key", "")
                issue_url = (
                    f"{jira_history._base_url}/browse/{issue_key}"
                    if jira_history._base_url and issue_key
                    else ""
                )

                kb_message_suffix = ""
                try:
                    from app.services.jira import JiraKBSyncService

                    kb_service = JiraKBSyncService(db_session)
                    kb_result = await kb_service.sync_after_create(
                        issue_id=issue_key,
                        issue_identifier=issue_key,
                        issue_title=final_summary,
                        description=final_description,
                        state="To Do",
                        connector_id=actual_connector_id,
                        search_space_id=search_space_id,
                        user_id=user_id,
                    )
                    if kb_result["status"] == "success":
                        kb_message_suffix = (
                            " Your knowledge base has also been updated."
                        )
                    else:
                        kb_message_suffix = " This issue will be added to your knowledge base in the next scheduled sync."
                except Exception as kb_err:
                    logger.warning(f"KB sync after create failed: {kb_err}")
                    kb_message_suffix = " This issue will be added to your knowledge base in the next scheduled sync."

                return {
                    "status": "success",
                    "issue_key": issue_key,
                    "issue_url": issue_url,
                    "message": f"Jira issue {issue_key} created successfully.{kb_message_suffix}",
                }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error(f"Error creating Jira issue: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while creating the issue.",
            }

    return create_jira_issue
