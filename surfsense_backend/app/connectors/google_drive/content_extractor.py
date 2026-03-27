"""Content extraction for Google Drive files."""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Log
from app.services.task_logging_service import TaskLoggingService

from .client import GoogleDriveClient
from .file_types import get_export_mime_type, is_google_workspace_file, should_skip_file

logger = logging.getLogger(__name__)


async def download_and_extract_content(
    client: GoogleDriveClient,
    file: dict[str, Any],
) -> tuple[str | None, dict[str, Any], str | None]:
    """Download a Google Drive file and extract its content as markdown.

    ETL only -- no DB writes, no indexing, no summarization.

    Returns:
        (markdown_content, drive_metadata, error_message)
        On success error_message is None.
    """
    file_id = file.get("id")
    file_name = file.get("name", "Unknown")
    mime_type = file.get("mimeType", "")

    if should_skip_file(mime_type):
        return None, {}, f"Skipping {mime_type}"

    logger.info(f"Downloading file for content extraction: {file_name} ({mime_type})")

    drive_metadata: dict[str, Any] = {
        "google_drive_file_id": file_id,
        "google_drive_file_name": file_name,
        "google_drive_mime_type": mime_type,
        "source_connector": "google_drive",
    }
    if "modifiedTime" in file:
        drive_metadata["modified_time"] = file["modifiedTime"]
    if "createdTime" in file:
        drive_metadata["created_time"] = file["createdTime"]
    if "size" in file:
        drive_metadata["file_size"] = file["size"]
    if "webViewLink" in file:
        drive_metadata["web_view_link"] = file["webViewLink"]
    if "md5Checksum" in file:
        drive_metadata["md5_checksum"] = file["md5Checksum"]
    if is_google_workspace_file(mime_type):
        drive_metadata["exported_as"] = "pdf"
        drive_metadata["original_workspace_type"] = mime_type.split(".")[-1]

    temp_file_path = None
    try:
        if is_google_workspace_file(mime_type):
            # Workspace files (Docs/Sheets/Slides) use export -- returns bytes
            # in one shot. These are typically small (a few MB as PDF/text).
            export_mime = get_export_mime_type(mime_type)
            if not export_mime:
                return None, drive_metadata, f"Cannot export Google Workspace type: {mime_type}"
            content_bytes, error = await client.export_google_file(file_id, export_mime)
            if error:
                return None, drive_metadata, error
            extension = ".pdf" if export_mime == "application/pdf" else ".txt"

            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
                tmp.write(content_bytes)
                temp_file_path = tmp.name
        else:
            # Binary files -- stream directly to disk in chunks to avoid
            # loading the entire file into memory.
            extension = Path(file_name).suffix or ".bin"
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
                temp_file_path = tmp.name

            error = await client.download_file_to_disk(file_id, temp_file_path)
            if error:
                return None, drive_metadata, error

        markdown = await _parse_file_to_markdown(temp_file_path, file_name)
        return markdown, drive_metadata, None

    except Exception as e:
        logger.warning(f"Failed to extract content from {file_name}: {e!s}")
        return None, drive_metadata, str(e)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass


async def _parse_file_to_markdown(file_path: str, filename: str) -> str:
    """Parse a local file to markdown using the configured ETL service."""
    lower = filename.lower()

    if lower.endswith((".md", ".markdown", ".txt")):
        with open(file_path, encoding="utf-8") as f:
            return f.read()

    if lower.endswith((".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm")):
        from app.config import config as app_config
        from litellm import atranscription

        stt_service_type = (
            "local"
            if app_config.STT_SERVICE and app_config.STT_SERVICE.startswith("local/")
            else "external"
        )
        if stt_service_type == "local":
            from app.services.stt_service import stt_service
            result = stt_service.transcribe_file(file_path)
            text = result.get("text", "")
        else:
            with open(file_path, "rb") as audio_file:
                kwargs: dict[str, Any] = {
                    "model": app_config.STT_SERVICE,
                    "file": audio_file,
                    "api_key": app_config.STT_SERVICE_API_KEY,
                }
                if app_config.STT_SERVICE_API_BASE:
                    kwargs["api_base"] = app_config.STT_SERVICE_API_BASE
                resp = await atranscription(**kwargs)
                text = resp.get("text", "")

        if not text:
            raise ValueError("Transcription returned empty text")
        return f"# Transcription of {filename}\n\n{text}"

    # Document files -- use configured ETL service
    from app.config import config as app_config

    if app_config.ETL_SERVICE == "UNSTRUCTURED":
        from langchain_unstructured import UnstructuredLoader
        from app.utils.document_converters import convert_document_to_markdown

        loader = UnstructuredLoader(
            file_path,
            mode="elements",
            post_processors=[],
            languages=["eng"],
            include_orig_elements=False,
            include_metadata=False,
            strategy="auto",
        )
        docs = await loader.aload()
        return await convert_document_to_markdown(docs)

    if app_config.ETL_SERVICE == "LLAMACLOUD":
        from app.tasks.document_processors.file_processors import (
            parse_with_llamacloud_retry,
        )

        result = await parse_with_llamacloud_retry(file_path=file_path, estimated_pages=50)
        markdown_documents = await result.aget_markdown_documents(split_by_page=False)
        if not markdown_documents:
            raise RuntimeError(f"LlamaCloud returned no documents for {filename}")
        return markdown_documents[0].text

    if app_config.ETL_SERVICE == "DOCLING":
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(file_path)
        return result.document.export_to_markdown()

    raise RuntimeError(f"Unknown ETL_SERVICE: {app_config.ETL_SERVICE}")


async def download_and_process_file(
    client: GoogleDriveClient,
    file: dict[str, Any],
    search_space_id: int,
    user_id: str,
    session: AsyncSession,
    task_logger: TaskLoggingService,
    log_entry: Log,
    connector_id: int | None = None,
    enable_summary: bool = True,
) -> tuple[Any, str | None, dict[str, Any] | None]:
    """
    Download Google Drive file and process using Surfsense file processors.

    Args:
        client: GoogleDriveClient instance
        file: File metadata from Drive API
        search_space_id: ID of the search space
        user_id: ID of the user
        session: Database session
        task_logger: Task logging service
        log_entry: Log entry for tracking
        connector_id: ID of the connector (for de-indexing support)

    Returns:
        Tuple of (Document object if successful, error message if failed, file metadata dict)
    """
    file_id = file.get("id")
    file_name = file.get("name", "Unknown")
    mime_type = file.get("mimeType", "")

    # Skip folders and shortcuts
    if should_skip_file(mime_type):
        return None, f"Skipping {mime_type}", None

    logger.info(f"Downloading file: {file_name} ({mime_type})")

    temp_file_path = None
    try:
        # Step 1: Download or export the file
        if is_google_workspace_file(mime_type):
            # Google Workspace files need export (as PDF to preserve formatting & images)
            export_mime = get_export_mime_type(mime_type)
            if not export_mime:
                return None, f"Cannot export Google Workspace type: {mime_type}"

            logger.info(f"Exporting Google Workspace file as {export_mime}")
            content_bytes, error = await client.export_google_file(file_id, export_mime)
            if error:
                return None, error

            extension = ".pdf" if export_mime == "application/pdf" else ".txt"
        else:
            content_bytes, error = await client.download_file(file_id)
            if error:
                return None, error

            # Preserve original file extension
            extension = Path(file_name).suffix or ".bin"

        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp_file:
            tmp_file.write(content_bytes)
            temp_file_path = tmp_file.name

        from app.db import DocumentType
        from app.tasks.document_processors.file_processors import (
            process_file_in_background,
        )

        connector_info = {
            "type": DocumentType.GOOGLE_DRIVE_FILE,
            "metadata": {
                "google_drive_file_id": file_id,
                "google_drive_file_name": file_name,
                "google_drive_mime_type": mime_type,
                "source_connector": "google_drive",
            },
        }
        # Include connector_id for de-indexing support
        connector_info["enable_summary"] = enable_summary
        if connector_id is not None:
            connector_info["connector_id"] = connector_id

        # Add additional Drive metadata if available
        if "modifiedTime" in file:
            connector_info["metadata"]["modified_time"] = file["modifiedTime"]
        if "createdTime" in file:
            connector_info["metadata"]["created_time"] = file["createdTime"]
        if "size" in file:
            connector_info["metadata"]["file_size"] = file["size"]
        if "webViewLink" in file:
            connector_info["metadata"]["web_view_link"] = file["webViewLink"]
        if "md5Checksum" in file:
            connector_info["metadata"]["md5_checksum"] = file["md5Checksum"]

        if is_google_workspace_file(mime_type):
            connector_info["metadata"]["exported_as"] = "pdf"
            connector_info["metadata"]["original_workspace_type"] = mime_type.split(
                "."
            )[-1]

        logger.info(f"Processing {file_name} with Surfsense's file processor")
        await process_file_in_background(
            file_path=temp_file_path,
            filename=file_name,
            search_space_id=search_space_id,
            user_id=user_id,
            session=session,
            task_logger=task_logger,
            log_entry=log_entry,
            connector=connector_info,
        )

        return None, None, connector_info["metadata"]

    except Exception as e:
        logger.warning(f"Failed to process {file_name}: {e!s}")
        return None, str(e), None

    finally:
        # Cleanup temp file (if process_file_in_background didn't already delete it)
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.debug(f"Could not delete temp file {temp_file_path}: {e}")
