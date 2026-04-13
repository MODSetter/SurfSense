import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import tool
from app.agents.new_chat.tools.hitl import request_approval
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connectors.dropbox.client import DropboxClient
from app.db import SearchSourceConnector, SearchSourceConnectorType

logger = logging.getLogger(__name__)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_FILE_TYPE_LABELS = {
    "paper": "Dropbox Paper (.paper)",
    "docx": "Word Document (.docx)",
}

_SUPPORTED_TYPES = [
    {"value": "paper", "label": "Dropbox Paper (.paper)"},
    {"value": "docx", "label": "Word Document (.docx)"},
]


def _ensure_extension(name: str, file_type: str) -> str:
    """Strip any existing extension and append the correct one."""
    stem = Path(name).stem
    ext = ".paper" if file_type == "paper" else ".docx"
    return f"{stem}{ext}"


def _markdown_to_docx(markdown_text: str) -> bytes:
    """Convert a markdown string to DOCX bytes using pypandoc."""
    import pypandoc

    fd, tmp_path = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    try:
        pypandoc.convert_text(
            markdown_text,
            "docx",
            format="gfm",
            extra_args=["--standalone"],
            outputfile=tmp_path,
        )
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)


def create_create_dropbox_file_tool(
    db_session: AsyncSession | None = None,
    search_space_id: int | None = None,
    user_id: str | None = None,
):
    @tool
    async def create_dropbox_file(
        name: str,
        file_type: Literal["paper", "docx"] = "paper",
        content: str | None = None,
    ) -> dict[str, Any]:
        """Create a new document in Dropbox.

        Use this tool when the user explicitly asks to create a new document
        in Dropbox. The user MUST specify a topic before you call this tool.

        Args:
            name: The document title (without extension).
            file_type: Either "paper" (Dropbox Paper, default) or "docx" (Word document).
            content: Optional initial content as markdown.

        Returns:
            Dictionary with status, file_id, name, web_url, and message.
        """
        logger.info(
            f"create_dropbox_file called: name='{name}', file_type='{file_type}'"
        )

        if db_session is None or search_space_id is None or user_id is None:
            return {
                "status": "error",
                "message": "Dropbox tool not properly configured.",
            }

        try:
            result = await db_session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.user_id == user_id,
                    SearchSourceConnector.connector_type
                    == SearchSourceConnectorType.DROPBOX_CONNECTOR,
                )
            )
            connectors = result.scalars().all()

            if not connectors:
                return {
                    "status": "error",
                    "message": "No Dropbox connector found. Please connect Dropbox in your workspace settings.",
                }

            accounts = []
            for c in connectors:
                cfg = c.config or {}
                accounts.append(
                    {
                        "id": c.id,
                        "name": c.name,
                        "user_email": cfg.get("user_email"),
                        "auth_expired": cfg.get("auth_expired", False),
                    }
                )

            if all(a.get("auth_expired") for a in accounts):
                return {
                    "status": "auth_error",
                    "message": "All connected Dropbox accounts need re-authentication.",
                    "connector_type": "dropbox",
                }

            parent_folders: dict[int, list[dict[str, str]]] = {}
            for acc in accounts:
                cid = acc["id"]
                if acc.get("auth_expired"):
                    parent_folders[cid] = []
                    continue
                try:
                    client = DropboxClient(session=db_session, connector_id=cid)
                    items, err = await client.list_folder("")
                    if err:
                        logger.warning(
                            "Failed to list folders for connector %s: %s", cid, err
                        )
                        parent_folders[cid] = []
                    else:
                        parent_folders[cid] = [
                            {
                                "folder_path": item.get("path_lower", ""),
                                "name": item["name"],
                            }
                            for item in items
                            if item.get(".tag") == "folder" and item.get("name")
                        ]
                except Exception:
                    logger.warning(
                        "Error fetching folders for connector %s", cid, exc_info=True
                    )
                    parent_folders[cid] = []

            context: dict[str, Any] = {
                "accounts": accounts,
                "parent_folders": parent_folders,
                "supported_types": _SUPPORTED_TYPES,
            }

            result = request_approval(
                action_type="dropbox_file_creation",
                tool_name="create_dropbox_file",
                params={
                    "name": name,
                    "file_type": file_type,
                    "content": content,
                    "connector_id": None,
                    "parent_folder_path": None,
                },
                context=context,
            )

            if result.rejected:
                return {
                    "status": "rejected",
                    "message": "User declined. Do not retry or suggest alternatives.",
                }

            final_name = result.params.get("name", name)
            final_file_type = result.params.get("file_type", file_type)
            final_content = result.params.get("content", content)
            final_connector_id = result.params.get("connector_id")
            final_parent_folder_path = result.params.get("parent_folder_path")

            if not final_name or not final_name.strip():
                return {"status": "error", "message": "File name cannot be empty."}

            final_name = _ensure_extension(final_name, final_file_type)

            if final_connector_id is not None:
                result = await db_session.execute(
                    select(SearchSourceConnector).filter(
                        SearchSourceConnector.id == final_connector_id,
                        SearchSourceConnector.search_space_id == search_space_id,
                        SearchSourceConnector.user_id == user_id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.DROPBOX_CONNECTOR,
                    )
                )
                connector = result.scalars().first()
            else:
                connector = connectors[0]

            if not connector:
                return {
                    "status": "error",
                    "message": "Selected Dropbox connector is invalid.",
                }

            client = DropboxClient(session=db_session, connector_id=connector.id)

            parent_path = final_parent_folder_path or ""
            file_path = (
                f"{parent_path}/{final_name}" if parent_path else f"/{final_name}"
            )

            if final_file_type == "paper":
                created = await client.create_paper_doc(file_path, final_content or "")
                file_id = created.get("file_id", "")
                web_url = created.get("url", "")
            else:
                docx_bytes = _markdown_to_docx(final_content or "")
                created = await client.upload_file(
                    file_path, docx_bytes, mode="add", autorename=True
                )
                file_id = created.get("id", "")
                web_url = ""

            logger.info(f"Dropbox file created: id={file_id}, name={final_name}")

            kb_message_suffix = ""
            try:
                from app.services.dropbox import DropboxKBSyncService

                kb_service = DropboxKBSyncService(db_session)
                kb_result = await kb_service.sync_after_create(
                    file_id=file_id,
                    file_name=final_name,
                    file_path=file_path,
                    web_url=web_url,
                    content=final_content,
                    connector_id=connector.id,
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
                "file_id": file_id,
                "name": final_name,
                "web_url": web_url,
                "message": f"Successfully created '{final_name}' in Dropbox.{kb_message_suffix}",
            }

        except Exception as e:
            from langgraph.errors import GraphInterrupt

            if isinstance(e, GraphInterrupt):
                raise
            logger.error(f"Error creating Dropbox file: {e}", exc_info=True)
            return {
                "status": "error",
                "message": "Something went wrong while creating the file. Please try again.",
            }

    return create_dropbox_file
