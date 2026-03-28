import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.types import interrupt
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

        Returns:
            Dictionary with status, file_id, deleted_from_kb, and message.
        """
        logger.info(f"delete_onedrive_file called: file_name='{file_name}', delete_from_kb={delete_from_kb}")

        if db_session is None or search_space_id is None or user_id is None:
            return {"status": "error", "message": "OneDrive tool not properly configured."}

        try:
            from sqlalchemy import String, cast

            doc_result = await db_session.execute(
                select(Document).where(
                    Document.search_space_id == search_space_id,
                    Document.document_type == DocumentType.ONEDRIVE_FILE,
                    Document.title == file_name,
                )
            )
            document = doc_result.scalars().first()

            if not document:
                doc_result = await db_session.execute(
                    select(Document).where(
                        Document.search_space_id == search_space_id,
                        Document.document_type == DocumentType.ONEDRIVE_FILE,
                        cast(Document.document_metadata["onedrive_file_name"], String) == file_name,
                    )
                )
                document = doc_result.scalars().first()

            if not document:
                return {"status": "not_found", "message": f"File '{file_name}' not found in your OneDrive knowledge base."}

            meta = document.document_metadata or {}
            file_id = meta.get("onedrive_file_id")
            connector_id = meta.get("connector_id")
            document_id = document.id

            if not file_id:
                return {"status": "error", "message": "File ID is missing. Please re-index the file."}

            conn_result = await db_session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == connector_id,
                    SearchSourceConnector.connector_type == SearchSourceConnectorType.ONEDRIVE_CONNECTOR,
                )
            )
            connector = conn_result.scalars().first()
            if not connector:
                return {"status": "error", "message": "OneDrive connector not found for this file."}

            cfg = connector.config or {}
            if cfg.get("auth_expired"):
                return {
                    "status": "auth_error",
                    "message": "OneDrive account needs re-authentication.",
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

            approval = interrupt(
                {
                    "type": "onedrive_file_trash",
                    "action": {
                        "tool": "delete_onedrive_file",
                        "params": {
                            "file_id": file_id,
                            "connector_id": connector_id,
                            "delete_from_kb": delete_from_kb,
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
                return {"status": "rejected", "message": "User declined. The file was not trashed."}

            final_params: dict[str, Any] = {}
            edited_action = decision.get("edited_action")
            if isinstance(edited_action, dict):
                edited_args = edited_action.get("args")
                if isinstance(edited_args, dict):
                    final_params = edited_args
            elif isinstance(decision.get("args"), dict):
                final_params = decision["args"]

            final_file_id = final_params.get("file_id", file_id)
            final_connector_id = final_params.get("connector_id", connector_id)
            final_delete_from_kb = final_params.get("delete_from_kb", delete_from_kb)

            client = OneDriveClient(session=db_session, connector_id=final_connector_id)
            await client.trash_file(final_file_id)

            logger.info(f"OneDrive file deleted (moved to recycle bin): file_id={final_file_id}")

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
                except Exception as e:
                    logger.error(f"Failed to delete document from KB: {e}")
                    await db_session.rollback()

            trash_result["deleted_from_kb"] = deleted_from_kb
            if deleted_from_kb:
                trash_result["message"] += " (also removed from knowledge base)"

            return trash_result

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error(f"Error deleting OneDrive file: {e}", exc_info=True)
            return {"status": "error", "message": "Something went wrong while trashing the file."}

    return delete_onedrive_file
