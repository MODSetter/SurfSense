"""Folder management for Google Drive."""

import logging
from typing import Any

from .client import GoogleDriveClient

logger = logging.getLogger(__name__)


async def list_folders(
    client: GoogleDriveClient,
    parent_id: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    List folders in Google Drive.

    Args:
        client: GoogleDriveClient instance
        parent_id: Parent folder ID (None for root)

    Returns:
        Tuple of (folders list, error message)
    """
    try:
        # Build query to get only folders
        query_parts = [
            "mimeType = 'application/vnd.google-apps.folder'",
            "trashed = false",
        ]

        if parent_id:
            query_parts.append(f"'{parent_id}' in parents")

        query = " and ".join(query_parts)

        folders, _, error = await client.list_files(
            query=query,
            fields="files(id, name, parents, createdTime, modifiedTime)",
            page_size=100,
        )

        if error:
            return [], error

        return folders, None

    except Exception as e:
        logger.error(f"Error listing folders: {e!s}", exc_info=True)
        return [], f"Error listing folders: {e!s}"


async def get_folder_hierarchy(
    client: GoogleDriveClient,
    folder_id: str,
) -> tuple[list[dict[str, str]], str | None]:
    """
    Get the full path hierarchy for a folder.

    Args:
        client: GoogleDriveClient instance
        folder_id: Folder ID to get hierarchy for

    Returns:
        Tuple of (hierarchy list [{'id': ..., 'name': ...}], error message)
    """
    try:
        hierarchy = []
        current_id = folder_id

        # Traverse up to root
        while current_id:
            file, error = await client.get_file_metadata(
                current_id, fields="id, name, parents, mimeType"
            )

            if error:
                return [], error

            if not file:
                break

            hierarchy.insert(0, {"id": file["id"], "name": file["name"]})

            # Get parent
            parents = file.get("parents", [])
            current_id = parents[0] if parents else None

        return hierarchy, None

    except Exception as e:
        logger.error(f"Error getting folder hierarchy: {e!s}", exc_info=True)
        return [], f"Error getting folder hierarchy: {e!s}"


async def get_files_in_folder(
    client: GoogleDriveClient,
    folder_id: str,
    include_subfolders: bool = True,
    page_token: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """
    Get all indexable files in a folder.

    Args:
        client: GoogleDriveClient instance
        folder_id: Folder ID to search in
        include_subfolders: Whether to include subfolders
        page_token: Pagination token

    Returns:
        Tuple of (files list, next_page_token, error message)
    """
    try:
        # Build query
        query_parts = [
            f"'{folder_id}' in parents",
            "trashed = false",
            "mimeType != 'application/vnd.google-apps.shortcut'",  # Skip shortcuts
        ]

        if not include_subfolders:
            query_parts.append("mimeType != 'application/vnd.google-apps.folder'")

        query = " and ".join(query_parts)

        files, next_token, error = await client.list_files(
            query=query,
            page_size=100,
            page_token=page_token,
        )

        if error:
            return [], None, error

        return files, next_token, None

    except Exception as e:
        logger.error(f"Error getting files in folder: {e!s}", exc_info=True)
        return [], None, f"Error getting files in folder: {e!s}"


async def get_file_by_id(
    client: GoogleDriveClient,
    file_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Get file metadata by ID.

    Args:
        client: GoogleDriveClient instance
        file_id: File ID to fetch

    Returns:
        Tuple of (file metadata dict, error message)
    """
    try:
        file, error = await client.get_file_metadata(
            file_id,
            fields="id, name, mimeType, parents, createdTime, modifiedTime, md5Checksum, size, webViewLink, iconLink",
        )

        if error:
            return None, error

        if not file:
            return None, f"File not found: {file_id}"

        return file, None

    except Exception as e:
        logger.error(f"Error getting file by ID: {e!s}", exc_info=True)
        return None, f"Error getting file by ID: {e!s}"


def format_folder_path(hierarchy: list[dict[str, str]]) -> str:
    """
    Format folder hierarchy as a path string.

    Args:
        hierarchy: List of folder dicts with 'id' and 'name'

    Returns:
        Formatted path (e.g., "My Drive / Projects / Documents")
    """
    if not hierarchy:
        return "My Drive"

    folder_names = [folder["name"] for folder in hierarchy]
    return " / ".join(folder_names)


async def list_folder_contents(
    client: GoogleDriveClient,
    parent_id: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    List folders and files in a Google Drive folder with pagination support.

    Args:
        client: GoogleDriveClient instance
        parent_id: Parent folder ID (None for root)

    Returns:
        Tuple of (items list with folders and files, error message)
    """
    try:
        # Build query to get folders and files (exclude shortcuts)
        query_parts = [
            "trashed = false",
            "mimeType != 'application/vnd.google-apps.shortcut'",
        ]

        # For root, we need to explicitly query for items in 'root'
        # For subfolders, query for items with that parent
        if parent_id:
            query_parts.append(f"'{parent_id}' in parents")
        else:
            # Query for root-level items
            query_parts.append("'root' in parents")

        query = " and ".join(query_parts)

        # Fetch all items with pagination (max 1000 per page)
        all_items = []
        page_token = None

        while True:
            items, next_token, error = await client.list_files(
                query=query,
                fields="files(id, name, mimeType, parents, createdTime, modifiedTime, md5Checksum, size, webViewLink, iconLink)",
                page_size=1000,  # Max allowed by Google Drive API
                page_token=page_token,
            )

            if error:
                return [], error

            all_items.extend(items)

            if not next_token:
                break

            page_token = next_token

        for item in all_items:
            item["isFolder"] = item["mimeType"] == "application/vnd.google-apps.folder"

        all_items.sort(key=lambda x: (not x["isFolder"], x["name"].lower()))

        folder_count = sum(1 for item in all_items if item["isFolder"])
        file_count = len(all_items) - folder_count

        logger.info(
            f"Listed {len(all_items)} items ({folder_count} folders, {file_count} files) "
            + (f"in folder {parent_id}" if parent_id else "in root (My Drive)")
        )

        return all_items, None

    except Exception as e:
        logger.error(f"Error listing folder contents: {e!s}", exc_info=True)
        return [], f"Error listing folder contents: {e!s}"
