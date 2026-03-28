"""Folder management for Microsoft OneDrive."""

import logging
from typing import Any

from .client import OneDriveClient
from .file_types import is_folder, should_skip_file

logger = logging.getLogger(__name__)


async def list_folder_contents(
    client: OneDriveClient,
    parent_id: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """List folders and files in a OneDrive folder.

    Returns (items list with folders first, error message).
    """
    try:
        items, error = await client.list_children(parent_id or "root")
        if error:
            return [], error

        for item in items:
            item["isFolder"] = is_folder(item)

        items.sort(key=lambda x: (not x["isFolder"], x.get("name", "").lower()))

        folder_count = sum(1 for item in items if item["isFolder"])
        file_count = len(items) - folder_count
        logger.info(
            f"Listed {len(items)} items ({folder_count} folders, {file_count} files) "
            + (f"in folder {parent_id}" if parent_id else "in root")
        )
        return items, None

    except Exception as e:
        logger.error(f"Error listing folder contents: {e!s}", exc_info=True)
        return [], f"Error listing folder contents: {e!s}"


async def get_files_in_folder(
    client: OneDriveClient,
    folder_id: str,
    include_subfolders: bool = True,
) -> tuple[list[dict[str, Any]], str | None]:
    """Get all indexable files in a folder, optionally recursing into subfolders."""
    try:
        items, error = await client.list_children(folder_id)
        if error:
            return [], error

        files: list[dict[str, Any]] = []
        for item in items:
            if is_folder(item):
                if include_subfolders:
                    sub_files, sub_error = await get_files_in_folder(
                        client, item["id"], include_subfolders=True
                    )
                    if sub_error:
                        logger.warning(f"Error recursing into folder {item.get('name')}: {sub_error}")
                        continue
                    files.extend(sub_files)
            elif not should_skip_file(item):
                files.append(item)

        return files, None

    except Exception as e:
        logger.error(f"Error getting files in folder: {e!s}", exc_info=True)
        return [], f"Error getting files in folder: {e!s}"


async def get_file_by_id(
    client: OneDriveClient,
    file_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Get file metadata by ID."""
    try:
        item, error = await client.get_item_metadata(file_id)
        if error:
            return None, error
        if not item:
            return None, f"File not found: {file_id}"
        return item, None

    except Exception as e:
        logger.error(f"Error getting file by ID: {e!s}", exc_info=True)
        return None, f"Error getting file by ID: {e!s}"
