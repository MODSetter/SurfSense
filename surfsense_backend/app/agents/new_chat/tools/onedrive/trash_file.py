import logging
from typing import Any

from langchain_core.tools import tool
from app.agents.new_chat.tools.hitl import request_approval
from sqlalchemy import String, and_, cast, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connectors.onedrive.client import OneDriveClient
from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)

logger = logging.getLogger(__name__)


def create_delete_onedrive_file_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def delete_onedrive_file(
        file_name: str,
        delete_from_kb: bool = False,
    ) -> dict[str, Any]:
        """Move a OneDrive file to the recycle bin.

        Use this tool when the user explicitly asks to delete, remove, or trash
        a file in OneDrive.

        Args:
            file_name: The exact name of the file to trash.
            delete_from_kb: Whether to also remove the file from the knowledge base.
                          Default is False.
                          Set to True to remove from both OneDrive and knowledge base.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "not_found", or "error"
            - file_id: OneDrive file ID (if success)
            - deleted_from_kb: whether the document was removed from the knowledge base
            - message: Result message

            IMPORTANT:
            - If status is "rejected", the user explicitly declined. Respond with a brief
              acknowledgment and do NOT retry or suggest alternatives.
            - If status is "not_found", relay the exact message to the user and ask them
              to verify the file name or check if it has been indexed.
        """
        logger.info(
            f"delete_onedrive_file called: file_name='{file_name}', delete_from_kb={delete_from_kb}"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "OneDrive tool not properly configured.",
            }

        try:
            doc_result = await db_session.execute(
                select(Document)
                .join(
                    SearchSourceConnector,
                    Document.connector_id == SearchSourceConnector.id,
                )
                .filter(
                    and_(
                        Document.search_space_id == search_space_id,
                        Document.document_type == DocumentType.ONEDRIVE_FILE,
                        func.lower(Document.title) == func.lower(file_name),
                        SearchSourceConnector.user_id == user_id,
                    )
                )
                .order_by(Document.updated_at.desc().nullslast())
                .limit(1)
            )
            document = doc_result.scalars().first()

            if not document:
                doc_result = await db_session.execute(
                    select(Document)
                    .join(
                        SearchSourceConnector,
                        Document.connector_id == SearchSourceConnector.id,
                    )
                    .filter(
                        and_(
                            Document.search_space_id == search_space_id,
                            Document.document_type == DocumentType.ONEDRIVE_FILE,
                            func.lower(
                                cast(
                                    Document.document_metadata["onedrive_file_name"],
                                    String,
                                )
                            )
                            == func.lower(file_name),
                            SearchSourceConnector.user_id == user_id,
                        )
                    )
                    .order_by(Document.updated_at.desc().nullslast())
                    .limit(1)
                )
                document = doc_result.scalars().first()

            if not document:
                return {
                    "status": "not_found",
                    "message": (
                        f"File '{file_name}' not found in your indexed OneDrive files. "
                        "This could mean: (1) the file doesn't exist, (2) it hasn't been indexed yet, "
                        "or (3) the file name is different."
                    ),
                }

            if not document.connector_id:
                return {
                    "status": "error",
                    "message": "Document has no associated connector.",
                }

            meta = document.document_metadata or {}
            file_id = meta.get("onedrive_file_id")
            document_id = document.id

            if not file_id:
                return {
                    "status": "error",
                    "message": "File ID is missing. Please re-index the file.",
                }

            conn_result = await db_session.execute(
                select(SearchSourceConnector).filter(
                    and_(
                        SearchSourceConnector.id == document.connector_id,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.ONEDRIVE_CONNECTOR,
                    )
                )
            )
            connector = conn_result.scalars().first()
            if not connector:
                return {
                    "status": "error",
                    "message": "OneDrive connector not found or access denied.",
                }

            cfg = connector.config or {}
            if cfg.get("auth_expired"):
                return {
                    "status": "auth_error",
                    "message": "OneDrive account needs re-authentication. Please re-authenticate in your connector settings.",
                    "connector_type": "onedrive",
                }

            context = {
                "file": {
                    "file_id": file_id,
                    "name": file_name,
                    "document_id": document_id,
                    "web_url": meta.get("web_url"),
                },
                "account": {
                    "id": connector.id,
                    "name": connector.name,
                    "user_email": cfg.get("user_email"),
                },
            }

            result = request_approval(
                action_type="onedrive_file_trash",
                tool_name="delete_onedrive_file",
                params={
                    "file_id": file_id,
                    "connector_id": connector.id,
                    "delete_from_kb": delete_from_kb,
                },
                context=context,
            )

            if result.rejected:
                return {
                    "status": "rejected",
                    "message": "User declined. Do not retry or suggest alternatives.",
                }

            final_file_id = result.params.get("file_id", file_id)
            final_connector_id = result.params.get("connector_id", connector.id)
            final_delete_from_kb = result.params.get("delete_from_kb", delete_from_kb)

            if final_connector_id != connector.id:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        and_(
                            SearchSourceConnector.id == final_connector_id,
                            SearchSourceConnector.search_space_id == search_space_id,
                            SearchSourceConnector.user_id == user_id,
                            SearchSourceConnector.connector_type
                            == SearchSourceConnectorType.ONEDRIVE_CONNECTOR,
                        )
                    )
                )
                validated_connector = result.scalars().first()
                if not validated_connector:
                    return {
                        "status": "error",
                        "message": "Selected OneDrive connector is invalid or has been disconnected.",
                    }
                actual_connector_id = validated_connector.id
            else:
                actual_connector_id = connector.id

            logger.info(
                f"Deleting OneDrive file: file_id='{final_file_id}', connector={actual_connector_id}"
            )

            client = OneDriveClient(
                session=db_session, connector_id=actual_connector_id
            )
            await client.trash_file(final_file_id)

            logger.info(
                f"OneDrive file deleted (moved to recycle bin): file_id={final_file_id}"
            )

            trash_result: dict[str, Any] = {
                "status": "success",
                "file_id": final_file_id,
                "message": f"Successfully moved '{file_name}' to the recycle bin.",
            }

            deleted_from_kb = False
            if final_delete_from_kb and document_id:
                try:
                    doc_result = await db_session.execute(
                        select(Document).filter(Document.id == document_id)
                    )
                    doc = doc_result.scalars().first()
                    if doc:
                        await db_session.delete(doc)
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
                        f"File moved to recycle bin, but failed to remove from knowledge base: {e!s}"
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
            logger.error(f"Error deleting OneDrive file: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while trashing the file. Please try again.",
            }

    return delete_onedrive_file
