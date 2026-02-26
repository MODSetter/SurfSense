import logging
from typing import Any, Literal

from googleapiclient.errors import HttpError
from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.google_drive.client import GoogleDriveClient
from app.connectors.google_drive.file_types import GOOGLE_DOC, GOOGLE_SHEET
from app.services.google_drive import GoogleDriveToolMetadataService

logger = logging.getLogger(__name__)

_MIME_MAP: dict[str, str] = {
    "google_doc": GOOGLE_DOC,
    "google_sheet": GOOGLE_SHEET,
}


def create_create_google_drive_file_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def create_google_drive_file(
        name: str,
        file_type: Literal["google_doc", "google_sheet"],
        content: str | None = None,
    ) -> dict[str, Any]:
        """Create a new Google Doc or Google Sheet in Google Drive.

        Use this tool when the user explicitly asks to create a new document
        or spreadsheet in Google Drive.

        Args:
            name: The file name (without extension).
            file_type: Either "google_doc" or "google_sheet".
            content: Optional initial content. For google_doc, provide markdown text.
                     For google_sheet, provide CSV-formatted text.

        Returns:
            Dictionary with:
            - status: "success", "rejected", or "error"
            - file_id: Google Drive file ID (if success)
            - name: File name (if success)
            - web_view_link: URL to open the file (if success)
            - message: Result message

            IMPORTANT:
            - If status is "rejected", the user explicitly declined the action.
              Respond with a brief acknowledgment and do NOT retry or suggest alternatives.
            - If status is "insufficient_permissions", the connector lacks the required OAuth scope.
              Inform the user they need to re-authenticate and do NOT retry the action.

        Examples:
            - "Create a Google Doc called 'Meeting Notes'"
            - "Create a spreadsheet named 'Budget 2026' with some sample data"
        """
        logger.info(
            f"create_google_drive_file called: name='{name}', type='{file_type}'"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Google Drive tool not properly configured. Please contact support.",
            }

        if file_type not in _MIME_MAP:
            return {
                "status": "error",
                "message": f"Unsupported file type '{file_type}'. Use 'google_doc' or 'google_sheet'.",
            }

        try:
            metadata_service = GoogleDriveToolMetadataService(db_session)
            context = await metadata_service.get_creation_context(
                search_space_id, user_id
            )

            if "error" in context:
                logger.error(f"Failed to fetch creation context: {context['error']}")
                return {"status": "error", "message": context["error"]}

            logger.info(
                f"Requesting approval for creating Google Drive file: name='{name}', type='{file_type}'"
            )
            approval = interrupt(
                {
                    "type": "google_drive_file_creation",
                    "action": {
                        "tool": "create_google_drive_file",
                        "params": {
                            "name": name,
                            "file_type": file_type,
                            "content": content,
                            "connector_id": None,
                            "parent_folder_id": None,
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
                return {
                    "status": "rejected",
                    "message": "User declined. The file was not created. Do not ask again or suggest alternatives.",
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
            final_file_type = final_params.get("file_type", file_type)
            final_content = final_params.get("content", content)
            final_connector_id = final_params.get("connector_id")
            final_parent_folder_id = final_params.get("parent_folder_id")

            if not final_name or not final_name.strip():
                return {"status": "error", "message": "File name cannot be empty."}

            mime_type = _MIME_MAP.get(final_file_type)
            if not mime_type:
                return {
                    "status": "error",
                    "message": f"Unsupported file type '{final_file_type}'.",
                }

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            if final_connector_id is not None:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == final_connector_id,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
                    )
                )
                connector = result.scalars().first()
                if not connector:
                    return {
                        "status": "error",
                        "message": "Selected Google Drive connector is invalid or has been disconnected.",
                    }
                actual_connector_id = connector.id
            else:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
                    )
                )
                connector = result.scalars().first()
                if not connector:
                    return {
                        "status": "error",
                        "message": "No Google Drive connector found. Please connect Google Drive in your workspace settings.",
                    }
                actual_connector_id = connector.id

            logger.info(
                f"Creating Google Drive file: name='{final_name}', type='{final_file_type}', connector={actual_connector_id}"
            )
            client = GoogleDriveClient(
                session=db_session, connector_id=actual_connector_id
            )
            try:
                created = await client.create_file(
                    name=final_name,
                    mime_type=mime_type,
                    parent_folder_id=final_parent_folder_id,
                    content=final_content,
                )
            except HttpError as http_err:
                if http_err.resp.status == 403:
                    logger.warning(
                        f"Insufficient permissions for connector {actual_connector_id}: {http_err}"
                    )
                    return {
                        "status": "insufficient_permissions",
                        "connector_id": actual_connector_id,
                        "message": "This Google Drive account needs additional permissions. Please re-authenticate.",
                    }
                raise

            logger.info(
                f"Google Drive file created: id={created.get('id')}, name={created.get('name')}"
            )
            return {
                "status": "success",
                "file_id": created.get("id"),
                "name": created.get("name"),
                "web_view_link": created.get("webViewLink"),
                "message": f"Successfully created '{created.get('name')}' in Google Drive.",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error creating Google Drive file: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while creating the file. Please try again.",
            }

    return create_google_drive_file
