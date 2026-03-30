import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt
from sqlalchemy import String, and_, cast, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connectors.dropbox.client import DropboxClient
from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
)

logger = logging.getLogger(__name__)


def create_delete_dropbox_file_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def delete_dropbox_file(
        file_name: str,
        delete_from_kb: bool = False,
    ) -> dict[str, Any]:
        """Delete a file from Dropbox.

        Use this tool when the user explicitly asks to delete, remove, or trash
        a file in Dropbox.

        Args:
            file_name: The exact name of the file to delete.
            delete_from_kb: Whether to also remove the file from the knowledge base.
                          Default is False.

        Returns:
            Dictionary with:
            - status: "success", "rejected", "not_found", or "error"
            - file_id: Dropbox file ID (if success)
            - deleted_from_kb: whether the document was removed from the knowledge base
            - message: Result message

            IMPORTANT:
            - If status is "rejected", the user explicitly declined. Respond with a brief
              acknowledgment and do NOT retry or suggest alternatives.
            - If status is "not_found", relay the exact message to the user and ask them
              to verify the file name or check if it has been indexed.
        """
        logger.info(
            f"delete_dropbox_file called: file_name='{file_name}', delete_from_kb={delete_from_kb}"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Dropbox tool not properly configured.",
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
                        Document.document_type == DocumentType.DROPBOX_FILE,
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
                            Document.document_type == DocumentType.DROPBOX_FILE,
                            func.lower(
                                cast(
                                    Document.document_metadata["dropbox_file_name"],
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
                        f"File '{file_name}' not found in your indexed Dropbox files. "
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
            file_path = meta.get("dropbox_path")
            file_id = meta.get("dropbox_file_id")
            document_id = document.id

            if not file_path:
                return {
                    "status": "error",
                    "message": "File path is missing. Please re-index the file.",
                }

            conn_result = await db_session.execute(
                select(SearchSourceConnector).filter(
                    and_(
                        SearchSourceConnector.id == document.connector_id,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.DROPBOX_CONNECTOR,
                    )
                )
            )
            connector = conn_result.scalars().first()
            if not connector:
                return {
                    "status": "error",
                    "message": "Dropbox connector not found or access denied.",
                }

            cfg = connector.config or {}
            if cfg.get("auth_expired"):
                return {
                    "status": "auth_error",
                    "message": "Dropbox account needs re-authentication. Please re-authenticate in your connector settings.",
                    "connector_type": "dropbox",
                }

            context = {
                "file": {
                    "file_id": file_id,
                    "file_path": file_path,
                    "name": file_name,
                    "document_id": document_id,
                },
                "account": {
                    "id": connector.id,
                    "name": connector.name,
                    "user_email": cfg.get("user_email"),
                },
            }

            approval = interrupt(
                {
                    "type": "dropbox_file_trash",
                    "action": {
                        "tool": "delete_dropbox_file",
                        "params": {
                            "file_path": file_path,
                            "connector_id": connector.id,
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
                return {"status": "error", "message": "No approval decision received"}

            decision = decisions[0]
            decision_type = decision.get("type") or decision.get("decision_type")
            logger.info(f"User decision: {decision_type}")

            if decision_type == "reject":
                return {
                    "status": "rejected",
                    "message": "User declined. The file was not deleted. Do not ask again or suggest alternatives.",
                }

            final_params: dict[str, Any] = {}
            edited_action = decision.get("edited_action")
            if isinstance(edited_action, dict):
                edited_args = edited_action.get("args")
                if isinstance(edited_args, dict):
                    final_params = edited_args
            elif isinstance(decision.get("args"), dict):
                final_params = decision["args"]

            final_file_path = final_params.get("file_path", file_path)
            final_connector_id = final_params.get("connector_id", connector.id)
            final_delete_from_kb = final_params.get("delete_from_kb", delete_from_kb)

            if final_connector_id != connector.id:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        and_(
                            SearchSourceConnector.id == final_connector_id,
                            SearchSourceConnector.search_space_id == search_space_id,
                            SearchSourceConnector.user_id == user_id,
                            SearchSourceConnector.connector_type
                            == SearchSourceConnectorType.DROPBOX_CONNECTOR,
                        )
                    )
                )
                validated_connector = result.scalars().first()
                if not validated_connector:
                    return {
                        "status": "error",
                        "message": "Selected Dropbox connector is invalid or has been disconnected.",
                    }
                actual_connector_id = validated_connector.id
            else:
                actual_connector_id = connector.id

            logger.info(
                f"Deleting Dropbox file: path='{final_file_path}', connector={actual_connector_id}"
            )

            client = DropboxClient(
                session=db_session, connector_id=actual_connector_id
            )
            await client.delete_file(final_file_path)

            logger.info(f"Dropbox file deleted: path={final_file_path}")

            trash_result: dict[str, Any] = {
                "status": "success",
                "file_id": file_id,
                "message": f"Successfully deleted '{file_name}' from Dropbox.",
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
                        f"File deleted, but failed to remove from knowledge base: {e!s}"
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
            logger.error(f"Error deleting Dropbox file: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while deleting the file. Please try again.",
            }

    return delete_dropbox_file
