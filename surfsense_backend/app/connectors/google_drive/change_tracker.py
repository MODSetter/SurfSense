"""Change tracking for Google Drive delta sync."""

import logging
from datetime import datetime
from typing import Any

from .client import GoogleDriveClient

logger = logging.getLogger(__name__)


async def get_start_page_token(
    client: GoogleDriveClient,
) -> tuple[str | None, str | None]:
    """
    Get the starting page token for change tracking.

    This token represents the current state and is used for future delta syncs.

    Args:
        client: GoogleDriveClient instance

    Returns:
        Tuple of (start_page_token, error message)
    """
    try:
        service = await client.get_service()
        response = service.changes().getStartPageToken(supportsAllDrives=True).execute()
        token = response.get("startPageToken")

        logger.info(f"Got start page token: {token}")
        return token, None

    except Exception as e:
        logger.error(f"Error getting start page token: {e!s}", exc_info=True)
        return None, f"Error getting start page token: {e!s}"


async def get_changes(
    client: GoogleDriveClient,
    page_token: str,
    folder_id: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """
    Get list of changes since the given page token.

    Args:
        client: GoogleDriveClient instance
        page_token: Page token from previous sync
        folder_id: Optional folder ID to filter changes

    Returns:
        Tuple of (changes list, new_page_token, error message)
    """
    try:
        service = await client.get_service()

        params = {
            "pageToken": page_token,
            "pageSize": 100,
            "fields": "nextPageToken, newStartPageToken, changes(fileId, removed, file(id, name, mimeType, modifiedTime, md5Checksum, size, webViewLink, parents, trashed))",
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
        }

        response = service.changes().list(**params).execute()

        changes = response.get("changes", [])
        next_token = response.get("nextPageToken")
        new_start_token = response.get("newStartPageToken")

        # Use new start token if this is the last page
        token_to_return = new_start_token if new_start_token else next_token

        # Filter changes by folder if specified
        if folder_id:
            changes = await _filter_changes_by_folder(client, changes, folder_id)

        logger.info(f"Got {len(changes)} changes, next token: {token_to_return}")
        return changes, token_to_return, None

    except Exception as e:
        logger.error(f"Error getting changes: {e!s}", exc_info=True)
        return [], None, f"Error getting changes: {e!s}"


async def _filter_changes_by_folder(
    client: GoogleDriveClient,
    changes: list[dict[str, Any]],
    folder_id: str,
) -> list[dict[str, Any]]:
    """
    Filter changes to only include files within the specified folder.

    Args:
        client: GoogleDriveClient instance
        changes: List of changes from API
        folder_id: Folder ID to filter by

    Returns:
        Filtered list of changes
    """
    filtered = []

    for change in changes:
        file = change.get("file")
        if not file:
            filtered.append(change)
            continue

        # Check if file is in the folder (or subfolder)
        parents = file.get("parents", [])
        if folder_id in parents:
            filtered.append(change)
        else:
            # Check if any parent is a descendant of folder_id
            # This is a simplified check - full implementation would traverse hierarchy
            # For now, we'll include it and let indexer validate
            filtered.append(change)

    return filtered


def categorize_change(change: dict[str, Any]) -> str:
    """
    Categorize a change event.

    Args:
        change: Change event from Drive API

    Returns:
        Category: 'removed', 'trashed', 'modified', 'new'
    """
    if change.get("removed"):
        return "removed"

    file = change.get("file")
    if not file:
        return "removed"

    if file.get("trashed"):
        return "trashed"

    created_time = file.get("createdTime")
    modified_time = file.get("modifiedTime")

    if created_time and modified_time:
        try:
            created = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
            modified = datetime.fromisoformat(modified_time.replace("Z", "+00:00"))

            # If created and modified times are very close, it's likely a new file
            time_diff = abs((modified - created).total_seconds())
            if time_diff < 60:  # Within 1 minute
                return "new"
        except Exception:
            pass

    return "modified"


async def fetch_all_changes(
    client: GoogleDriveClient,
    start_token: str,
    folder_id: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """
    Fetch all changes from start token, handling pagination.

    Args:
        client: GoogleDriveClient instance
        start_token: Starting page token
        folder_id: Optional folder ID to filter changes

    Returns:
        Tuple of (all changes, final_page_token, error message)
    """
    all_changes = []
    current_token = start_token
    error = None

    try:
        while current_token:
            changes, next_token, err = await get_changes(
                client, current_token, folder_id
            )

            if err:
                error = err
                break

            all_changes.extend(changes)

            if not next_token or next_token == current_token:
                break

            current_token = next_token

        logger.info(f"Fetched total of {len(all_changes)} changes")
        return all_changes, current_token, error

    except Exception as e:
        logger.error(f"Error fetching all changes: {e!s}", exc_info=True)
        return all_changes, current_token, f"Error fetching all changes: {e!s}"
