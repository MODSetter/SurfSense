import logging
from typing import Any, Literal

from googleapiclient.errors import HttpError
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.hitl import request_approval
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
        or spreadsheet in Google Drive. The user MUST specify a topic before
        you call this tool. If the request does not contain a topic (e.g.
        "create a drive doc" or "make a Google Sheet"), ask what the file
        should be about. Never call this tool without a clear topic from the user.

        Args:
            name: The file name (without extension).
            file_type: Either "google_doc" or "google_sheet".
            content: Optional initial content. Generate from the user's topic.
                     For google_doc, provide markdown text. For google_sheet, provide CSV-formatted text.

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
            - "Create a Google Doc with today's meeting notes"
            - "Create a spreadsheet for the 2026 budget"
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

            accounts = context.get("accounts", [])
            if accounts and all(a.get("auth_expired") for a in accounts):
                logger.warning("All Google Drive accounts have expired authentication")
                return {
                    "status": "auth_error",
                    "message": "All connected Google Drive accounts need re-authentication. Please re-authenticate in your connector settings.",
                    "connector_type": "google_drive",
                }

            logger.info(
                f"Requesting approval for creating Google Drive file: name='{name}', type='{file_type}'"
            )
            result = request_approval(
                action_type="google_drive_file_creation",
                tool_name="create_google_drive_file",
                params={
                    "name": name,
                    "file_type": file_type,
                    "content": content,
                    "connector_id": None,
                    "parent_folder_id": None,
                },
                context=context,
            )

            if result.rejected:
                return {
                    "status": "rejected",
                    "message": "User declined. The file was not created. Do not ask again or suggest alternatives.",
                }

            final_name = result.params.get("name", name)
            final_file_type = result.params.get("file_type", file_type)
            final_content = result.params.get("content", content)
            final_connector_id = result.params.get("connector_id")
            final_parent_folder_id = result.params.get("parent_folder_id")

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

            _drive_types = [
                SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
                SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
            ]

            if final_connector_id is not None:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == final_connector_id,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type.in_(_drive_types),
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
                        SearchSourceConnector.connector_type.in_(_drive_types),
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

            pre_built_creds = None
            if (
                connector.connector_type
                == SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR
            ):
                from app.utils.google_credentials import build_composio_credentials

                cca_id = connector.config.get("composio_connected_account_id")
                if cca_id:
                    pre_built_creds = build_composio_credentials(cca_id)

            client = GoogleDriveClient(
                session=db_session,
                connector_id=actual_connector_id,
                credentials=pre_built_creds,
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
                    try:
                        from sqlalchemy.orm.attributes import flag_modified

                        _res = await db_session.execute(
                            select(SearchSourceConnector).where(
                                SearchSourceConnector.id == actual_connector_id
                            )
                        )
                        _conn = _res.scalar_one_or_none()
                        if _conn and not _conn.config.get("auth_expired"):
                            _conn.config = {**_conn.config, "auth_expired": True}
                            flag_modified(_conn, "config")
                            await db_session.commit()
                    except Exception:
                        logger.warning(
                            "Failed to persist auth_expired for connector %s",
                            actual_connector_id,
                            exc_info=True,
                        )
                    return {
                        "status": "insufficient_permissions",
                        "connector_id": actual_connector_id,
                        "message": "This Google Drive account needs additional permissions. Please re-authenticate in connector settings.",
                    }
                raise

            logger.info(
                f"Google Drive file created: id={created.get('id')}, name={created.get('name')}"
            )

            kb_message_suffix = ""
            try:
                from app.services.google_drive import GoogleDriveKBSyncService

                kb_service = GoogleDriveKBSyncService(db_session)
                kb_result = await kb_service.sync_after_create(
                    file_id=created.get("id"),
                    file_name=created.get("name", final_name),
                    mime_type=mime_type,
                    web_view_link=created.get("webViewLink"),
                    content=final_content,
                    connector_id=actual_connector_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                )
                if kb_result["status"] == "success":
                    kb_message_suffix = " Your knowledge base has also been updated."
                else:
                    kb_message_suffix = " This file will be added to your knowledge base in the next scheduled sync."
            except Exception as kb_err:
                logger.warning(f"KB sync after create failed: {kb_err}")
                kb_message_suffix = " This file will be added to your knowledge base in the next scheduled sync."

            return {
                "status": "success",
                "file_id": created.get("id"),
                "name": created.get("name"),
                "web_view_link": created.get("webViewLink"),
                "message": f"Successfully created '{created.get('name')}' in Google Drive.{kb_message_suffix}",
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
