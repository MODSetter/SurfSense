"""Content extraction for Dropbox files.

Reuses the same ETL parsing logic as OneDrive/Google Drive since file parsing
is extension-based, not provider-specific.
"""

import contextlib
import logging
import os
import tempfile
from typing import Any

from .client import DropboxClient
from .file_types import get_extension_from_name, is_paper_file, should_skip_file

logger = logging.getLogger(__name__)


async def _export_paper_content(
    client: DropboxClient,
    file: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[str | None, dict[str, Any], str | None]:
    """Export a Dropbox Paper doc as markdown via ``/2/files/export``."""
    file_path_lower = file.get("path_lower", "")
    file_name = file.get("name", "Unknown")

    logger.info(f"Exporting Paper doc as markdown: {file_name}")

    content_bytes, error = await client.export_file(
        file_path_lower, export_format="markdown"
    )
    if error:
        return None, metadata, error
    if not content_bytes:
        return None, metadata, "Export returned empty content"

    markdown = content_bytes.decode("utf-8", errors="replace")
    metadata["exported_as"] = "markdown"
    metadata["original_type"] = "paper"
    return markdown, metadata, None


async def download_and_extract_content(
    client: DropboxClient,
    file: dict[str, Any],
) -> tuple[str | None, dict[str, Any], str | None]:
    """Download a Dropbox file and extract its content as markdown.

    Returns (markdown_content, dropbox_metadata, error_message).
    """
    file_path_lower = file.get("path_lower", "")
    file_name = file.get("name", "Unknown")
    file_id = file.get("id", "")

    if should_skip_file(file):
        return None, {}, "Skipping non-indexable item"

    logger.info(f"Downloading file for content extraction: {file_name}")

    metadata: dict[str, Any] = {
        "dropbox_file_id": file_id,
        "dropbox_file_name": file_name,
        "dropbox_path": file_path_lower,
        "source_connector": "dropbox",
    }

    if "server_modified" in file:
        metadata["modified_time"] = file["server_modified"]
    if "client_modified" in file:
        metadata["created_time"] = file["client_modified"]
    if "size" in file:
        metadata["file_size"] = file["size"]
    if "content_hash" in file:
        metadata["content_hash"] = file["content_hash"]

    if is_paper_file(file):
        return await _export_paper_content(client, file, metadata)

    temp_file_path = None
    try:
        extension = get_extension_from_name(file_name) or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            temp_file_path = tmp.name

        error = await client.download_file_to_disk(file_path_lower, temp_file_path)
        if error:
            return None, metadata, error

        from app.connectors.onedrive.content_extractor import _parse_file_to_markdown

        markdown = await _parse_file_to_markdown(temp_file_path, file_name)
        return markdown, metadata, None

    except Exception as e:
        logger.warning(f"Failed to extract content from {file_name}: {e!s}")
        return None, metadata, str(e)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            with contextlib.suppress(Exception):
                os.unlink(temp_file_path)
