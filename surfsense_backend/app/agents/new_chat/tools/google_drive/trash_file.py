import logging
from typing import Any

from googleapiclient.errors import HttpError
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.hitl import request_approval
from app.connectors.google_drive.client import GoogleDriveClient
from app.services.google_drive import GoogleDriveToolMetadataService

logger = logging.getLogger(__name__)


def create_delete_google_drive_file_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def delete_google_drive_file(
        file_name: str,
        delete_from_kb: bool = False,
    ) -> dict[str, Any]:
        """Move a Google Drive file to trash.

        Use this tool when the user explicitly asks to delete, remove, or trash
        a file in Google Drive.

        Args:
            file_name: The exact name of the file to trash (as it appears in Drive).
            delete_from_kb: Whether to also remove the file from the knowledge base.
                          Default is False.
                          Set to True to remove from both Google Drive and knowledge base.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "not_found", or "error"
            - file_id: Google Drive file ID (if success)
            - deleted_from_kb: whether the document was removed from the knowledge base
            - message: Result message

            IMPORTANT:
            - If status is "rejected", the user explicitly declined. Respond with a brief
              acknowledgment and do NOT retry or suggest alternatives.
            - If status is "not_found", relay the exact message to the user and ask them
              to verify the file name or check if it has been indexed.
            - If status is "insufficient_permissions", the connector lacks the required OAuth scope.
              Inform the user they need to re-authenticate and do NOT retry this tool.
        Examples:
            - "Delete the 'Meeting Notes' file from Google Drive"
            - "Trash the 'Old Budget' spreadsheet"
        """
        logger.info(
            f"delete_google_drive_file called: file_name='{file_name}', delete_from_kb={delete_from_kb}"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Google Drive tool not properly configured. Please contact support.",
            }

        try:
            metadata_service = GoogleDriveToolMetadataService(db_session)
            context = await metadata_service.get_trash_context(
                search_space_id, user_id, file_name
            )

            if "error" in context:
                error_msg = context["error"]
                if "not found" in error_msg.lower():
                    logger.warning(f"File not found: {error_msg}")
                    return {"status": "not_found", "message": error_msg}
                logger.error(f"Failed to fetch trash context: {error_msg}")
                return {"status": "error", "message": error_msg}

            account = context.get("account", {})
            if account.get("auth_expired"):
                logger.warning(
                    "Google Drive account %s has expired authentication",
                    account.get("id"),
                )
                return {
                    "status": "auth_error",
                    "message": "The Google Drive account for this file needs re-authentication. Please re-authenticate in your connector settings.",
                    "connector_type": "google_drive",
                }

            file = context["file"]
            file_id = file["file_id"]
            document_id = file.get("document_id")
            connector_id_from_context = context["account"]["id"]

            if not file_id:
                return {
                    "status": "error",
                    "message": "File ID is missing from the indexed document. Please re-index the file and try again.",
                }

            logger.info(
                f"Requesting approval for deleting Google Drive file: '{file_name}' (file_id={file_id}, delete_from_kb={delete_from_kb})"
            )
            result = request_approval(
                action_type="google_drive_file_trash",
                tool_name="delete_google_drive_file",
                params={
                    "file_id": file_id,
                    "connector_id": connector_id_from_context,
                    "delete_from_kb": delete_from_kb,
                },
                context=context,
            )

            if result.rejected:
                return {
                    "status": "rejected",
                    "message": "User declined. The file was not trashed. Do not ask again or suggest alternatives.",
                }

            final_file_id = result.params.get("file_id", file_id)
            final_connector_id = result.params.get(
                "connector_id", connector_id_from_context
            )
            final_delete_from_kb = result.params.get("delete_from_kb", delete_from_kb)

            if not final_connector_id:
                return {
                    "status": "error",
                    "message": "No connector found for this file.",
                }

            from sqlalchemy.future import select

            from app.db import SearchSourceConnector, SearchSourceConnectorType

            _drive_types = [
                SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
                SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
            ]

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

            logger.info(
                f"Deleting Google Drive file: file_id='{final_file_id}', connector={final_connector_id}"
            )

            is_composio_drive = (
                connector.connector_type
                == SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR
            )
            if is_composio_drive:
                cca_id = connector.config.get("composio_connected_account_id")
                if not cca_id:
                    return {
                        "status": "error",
                        "message": "Composio connected account ID not found for this Drive connector.",
                    }

            client = GoogleDriveClient(
                session=db_session,
                connector_id=connector.id,
            )
            try:
                if is_composio_drive:
                    from app.services.composio_service import ComposioService

                    result = await ComposioService().execute_tool(
                        connected_account_id=cca_id,
                        tool_name="GOOGLEDRIVE_TRASH_FILE",
                        params={"file_id": final_file_id},
                        entity_id=f"surfsense_{user_id}",
                    )
                    if not result.get("success"):
                        raise RuntimeError(
                            result.get("error", "Unknown Composio Drive error")
                        )
                else:
                    await client.trash_file(file_id=final_file_id)
            except HttpError as http_err:
                if http_err.resp.status == 403:
                    logger.warning(
                        f"Insufficient permissions for connector {connector.id}: {http_err}"
                    )
                    try:
                        from sqlalchemy.orm.attributes import flag_modified

                        if not connector.config.get("auth_expired"):
                            connector.config = {
                                **connector.config,
                                "auth_expired": True,
                            }
                            flag_modified(connector, "config")
                            await db_session.commit()
                    except Exception:
                        logger.warning(
                            "Failed to persist auth_expired for connector %s",
                            connector.id,
                            exc_info=True,
                        )
                    return {
                        "status": "insufficient_permissions",
                        "connector_id": connector.id,
                        "message": "This Google Drive account needs additional permissions. Please re-authenticate in connector settings.",
                    }
                raise

            logger.info(
                f"Google Drive file deleted (moved to trash): file_id={final_file_id}"
            )

            trash_result: dict[str, Any] = {
                "status": "success",
                "file_id": final_file_id,
                "message": f"Successfully moved '{file['name']}' to trash.",
            }

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
                        logger.info(
                            f"Deleted document {document_id} from knowledge base"
                        )
                    else:
                        logger.warning(f"Document {document_id} not found in KB")
                except Exception as e:
                    logger.error(f"Failed to delete document from KB: {e}")
                    await db_session.rollback()
                    trash_result["warning"] = (
                        f"File moved to trash, but failed to remove from knowledge base: {e!s}"
                    )

            trash_result["deleted_from_kb"] = deleted_from_kb
            if deleted_from_kb:
                trash_result["message"] = (
                    f"{trash_result.get('message', '')} (also removed from knowledge base)"
                )

            return trash_result

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise

            logger.error(f"Error deleting Google Drive file: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while trashing the file. Please try again.",
            }

    return delete_google_drive_file
