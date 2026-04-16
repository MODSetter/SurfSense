"""Content extraction for Google Drive files."""

import contextlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Log
from app.services.task_logging_service import TaskLoggingService

from .client import GoogleDriveClient
from .file_types import (
    get_export_mime_type,
    get_extension_from_mime,
    is_google_workspace_file,
    should_skip_by_extension,
    should_skip_file,
)

logger = logging.getLogger(__name__)


async def download_and_extract_content(
    client: GoogleDriveClient,
    file: dict[str, Any],
    *,
    vision_llm=None,
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

    if not is_google_workspace_file(mime_type):
        ext_skip, _unsup_ext = should_skip_by_extension(file_name)
        if ext_skip:
            return None, {}, f"Skipping unsupported extension: {file_name}"

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
        export_ext = get_extension_from_mime(get_export_mime_type(mime_type) or "")
        drive_metadata["exported_as"] = export_ext.lstrip(".") if export_ext else "pdf"
        drive_metadata["original_workspace_type"] = mime_type.split(".")[-1]

    temp_file_path = None
    try:
        if is_google_workspace_file(mime_type):
            export_mime = get_export_mime_type(mime_type)
            if not export_mime:
                return (
                    None,
                    drive_metadata,
                    f"Cannot export Google Workspace type: {mime_type}",
                )
            content_bytes, error = await client.export_google_file(file_id, export_mime)
            if error:
                return None, drive_metadata, error
            extension = get_extension_from_mime(export_mime) or ".pdf"

            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
                tmp.write(content_bytes)
                temp_file_path = tmp.name
        else:
            extension = (
                Path(file_name).suffix or get_extension_from_mime(mime_type) or ".bin"
            )
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
                temp_file_path = tmp.name

            error = await client.download_file_to_disk(file_id, temp_file_path)
            if error:
                return None, drive_metadata, error

        etl_filename = (
            file_name + extension if is_google_workspace_file(mime_type) else file_name
        )
        markdown = await _parse_file_to_markdown(
            temp_file_path, etl_filename, vision_llm=vision_llm
        )
        return markdown, drive_metadata, None

    except Exception as e:
        logger.warning(f"Failed to extract content from {file_name}: {e!s}")
        return None, drive_metadata, str(e)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            with contextlib.suppress(Exception):
                os.unlink(temp_file_path)


async def _parse_file_to_markdown(
    file_path: str, filename: str, *, vision_llm=None
) -> str:
    """Parse a local file to markdown using the unified ETL pipeline."""
    from app.etl_pipeline.etl_document import EtlRequest
    from app.etl_pipeline.etl_pipeline_service import EtlPipelineService

    result = await EtlPipelineService(vision_llm=vision_llm).extract(
        EtlRequest(file_path=file_path, filename=filename)
    )
    return result.markdown_content


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

    if should_skip_file(mime_type):
        return None, f"Skipping {mime_type}", None

    if not is_google_workspace_file(mime_type):
        ext_skip, _unsup_ext = should_skip_by_extension(file_name)
        if ext_skip:
            return None, f"Skipping unsupported extension: {file_name}", None

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

            extension = get_extension_from_mime(export_mime) or ".pdf"
        else:
            content_bytes, error = await client.download_file(file_id)
            if error:
                return None, error

            extension = (
                Path(file_name).suffix or get_extension_from_mime(mime_type) or ".bin"
            )

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
            export_ext = get_extension_from_mime(get_export_mime_type(mime_type) or "")
            connector_info["metadata"]["exported_as"] = (
                export_ext.lstrip(".") if export_ext else "pdf"
            )
            connector_info["metadata"]["original_workspace_type"] = mime_type.split(
                "."
            )[-1]

        etl_filename = (
            file_name + extension if is_google_workspace_file(mime_type) else file_name
        )
        logger.info(f"Processing {file_name} with Surfsense's file processor")
        await process_file_in_background(
            file_path=temp_file_path,
            filename=etl_filename,
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
