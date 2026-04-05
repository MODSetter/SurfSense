"""Content extraction for OneDrive files."""

import contextlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from .client import OneDriveClient
from .file_types import get_extension_from_mime, should_skip_file

logger = logging.getLogger(__name__)


async def download_and_extract_content(
    client: OneDriveClient,
    file: dict[str, Any],
) -> tuple[str | None, dict[str, Any], str | None]:
    """Download a OneDrive file and extract its content as markdown.

    Returns (markdown_content, onedrive_metadata, error_message).
    """
    item_id = file.get("id")
    file_name = file.get("name", "Unknown")

    if should_skip_file(file):
        return None, {}, "Skipping non-indexable item"

    file_info = file.get("file", {})
    mime_type = file_info.get("mimeType", "")

    logger.info(f"Downloading file for content extraction: {file_name} ({mime_type})")

    metadata: dict[str, Any] = {
        "onedrive_file_id": item_id,
        "onedrive_file_name": file_name,
        "onedrive_mime_type": mime_type,
        "source_connector": "onedrive",
    }
    if "lastModifiedDateTime" in file:
        metadata["modified_time"] = file["lastModifiedDateTime"]
    if "createdDateTime" in file:
        metadata["created_time"] = file["createdDateTime"]
    if "size" in file:
        metadata["file_size"] = file["size"]
    if "webUrl" in file:
        metadata["web_url"] = file["webUrl"]
    file_hashes = file_info.get("hashes", {})
    if file_hashes.get("sha256Hash"):
        metadata["sha256_hash"] = file_hashes["sha256Hash"]
    elif file_hashes.get("quickXorHash"):
        metadata["quick_xor_hash"] = file_hashes["quickXorHash"]

    temp_file_path = None
    try:
        extension = (
            Path(file_name).suffix or get_extension_from_mime(mime_type) or ".bin"
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            temp_file_path = tmp.name

        error = await client.download_file_to_disk(item_id, temp_file_path)
        if error:
            return None, metadata, error

        markdown = await _parse_file_to_markdown(temp_file_path, file_name)
        return markdown, metadata, None

    except Exception as e:
        logger.warning(f"Failed to extract content from {file_name}: {e!s}")
        return None, metadata, str(e)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            with contextlib.suppress(Exception):
                os.unlink(temp_file_path)


async def _parse_file_to_markdown(file_path: str, filename: str) -> str:
    """Parse a local file to markdown using the unified ETL pipeline."""
    from app.etl_pipeline.etl_document import EtlRequest
    from app.etl_pipeline.etl_pipeline_service import EtlPipelineService

    result = await EtlPipelineService().extract(
        EtlRequest(file_path=file_path, filename=filename)
    )
    return result.markdown_content
