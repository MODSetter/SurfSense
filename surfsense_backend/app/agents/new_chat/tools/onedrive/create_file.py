import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connectors.onedrive.client import OneDriveClient
from app.db import SearchSourceConnector, SearchSourceConnectorType

logger = logging.getLogger(__name__)


def create_create_onedrive_file_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def create_onedrive_file(
        name: str,
        content: str | None = None,
    ) -> dict[str, Any]:
        """Create a new file in Microsoft OneDrive.

        Use this tool when the user explicitly asks to create a new document
        in OneDrive. The user MUST specify a topic before you call this tool.

        Args:
            name: The file name (with extension, e.g. "notes.txt" or "report.docx").
            content: Optional initial content as plain text or markdown.

        Returns:
            Dictionary with status, file_id, name, web_url, and message.
        """
        logger.info(f"create_onedrive_file called: name='{name}'")

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "OneDrive tool not properly configured.",
            }

        try:
            result = await db_session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type == SearchSourceConnectorType.ONEDRIVE_CONNECTOR,
                )
            )
            connectors = result.scalars().all()

            if not connectors:
                return {
                    "status": "error",
                    "message": "No OneDrive connector found. Please connect OneDrive in your workspace settings.",
                }

            accounts = []
            for c in connectors:
                cfg = c.config or {}
                accounts.append({
                    "id": c.id,
                    "name": c.name,
                    "user_email": cfg.get("user_email"),
                    "auth_expired": cfg.get("auth_expired", False),
                })

            if all(a.get("auth_expired") for a in accounts):
                return {
                    "status": "auth_error",
                    "message": "All connected OneDrive accounts need re-authentication.",
                    "connector_type": "onedrive",
                }

            context = {"accounts": accounts}

            approval = interrupt(
                {
                    "type": "onedrive_file_creation",
                    "action": {
                        "tool": "create_onedrive_file",
                        "params": {
                            "name": name,
                            "content": content,
                            "connector_id": None,
                            "parent_folder_id": None,
                        },
                    },
                    "context": context,
                }
            )

            decisions_raw = approval.get("decisions", []) if isinstance(approval, dict) else []
            decisions = decisions_raw if isinstance(decisions_raw, list) else [decisions_raw]
            decisions = [d for d in decisions if isinstance(d, dict)]
            if not decisions:
                return {"status": "error", "message": "No approval decision received"}

            decision = decisions[0]
            decision_type = decision.get("type") or decision.get("decision_type")

            if decision_type == "reject":
                return {
                    "status": "rejected",
                    "message": "User declined. The file was not created.",
                }

            final_params: dict[str, Any] = {}
            edited_action = decision.get("edited_action")
            if isinstance(edited_action, dict):
                edited_args = edited_action.get("args")
                if isinstance(edited_args, dict):
                    final_params = edited_args
            elif isinstance(decision.get("args"), dict):
                final_params = decision["args"]

            final_name = final_params.get("name", name)
            final_content = final_params.get("content", content)
            final_connector_id = final_params.get("connector_id")
            final_parent_folder_id = final_params.get("parent_folder_id")

            if not final_name or not final_name.strip():
                return {"status": "error", "message": "File name cannot be empty."}

            if final_connector_id is not None:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == final_connector_id,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type == SearchSourceConnectorType.ONEDRIVE_CONNECTOR,
                    )
                )
                connector = result.scalars().first()
            else:
                connector = connectors[0]

            if not connector:
                return {"status": "error", "message": "Selected OneDrive connector is invalid."}

            client = OneDriveClient(session=db_session, connector_id=connector.id)
            created = await client.create_file(
                name=final_name,
                parent_id=final_parent_folder_id,
                content=final_content,
            )

            logger.info(f"OneDrive file created: id={created.get('id')}, name={created.get('name')}")

            return {
                "status": "success",
                "file_id": created.get("id"),
                "name": created.get("name"),
                "web_url": created.get("webUrl"),
                "message": f"Successfully created '{created.get('name')}' in OneDrive.",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error(f"Error creating OneDrive file: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while creating the file. Please try again.",
            }

    return create_onedrive_file
