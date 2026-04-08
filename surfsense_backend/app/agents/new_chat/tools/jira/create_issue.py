import asyncio
import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.connectors.jira_history import JiraHistoryConnector
from app.services.jira import JiraToolMetadataService

logger = logging.getLogger(__name__)


def create_create_jira_issue_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
    connector_id: int | None = None,
):
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

        if db_session is None or search_space_id is None or user_id is None:
            return {"status": "error", "message": "Jira tool not properly configured."}

        try:
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

            approval = interrupt(
                {
                    "type": "jira_issue_creation",
                    "action": {
                        "tool": "create_jira_issue",
                        "params": {
                            "project_key": project_key,
                            "summary": summary,
                            "issue_type": issue_type,
                            "description": description,
                            "priority": priority,
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
                return {"status": "error", "message": "No approval decision received"}

            decision = decisions[0]
            decision_type = decision.get("type") or decision.get("decision_type")

            if decision_type == "reject":
                return {
                    "status": "rejected",
                    "message": "User declined. The issue was not created.",
                }

            final_params: dict[str, Any] = {}
            edited_action = decision.get("edited_action")
            if isinstance(edited_action, dict):
                edited_args = edited_action.get("args")
                if isinstance(edited_args, dict):
                    final_params = edited_args
            elif isinstance(decision.get("args"), dict):
                final_params = decision["args"]

            final_project_key = final_params.get("project_key", project_key)
            final_summary = final_params.get("summary", summary)
            final_issue_type = final_params.get("issue_type", issue_type)
            final_description = final_params.get("description", description)
            final_priority = final_params.get("priority", priority)
            final_connector_id = final_params.get("connector_id", connector_id)

            if not final_summary or not final_summary.strip():
                return {"status": "error", "message": "Issue summary cannot be empty."}
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
                    return {"status": "error", "message": "No Jira connector found."}
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
                    kb_message_suffix = " Your knowledge base has also been updated."
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
