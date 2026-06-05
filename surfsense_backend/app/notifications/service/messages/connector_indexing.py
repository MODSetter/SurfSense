"""Pure presentation logic for connector-indexing notifications."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def operation_id(
    connector_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Build a unique id for a connector indexing run."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    date_range = ""
    if start_date or end_date:
        date_range = f"_{start_date or 'none'}_{end_date or 'none'}"
    return f"connector_{connector_id}_{timestamp}{date_range}"


def google_drive_operation_id(
    connector_id: int, folder_count: int, file_count: int
) -> str:
    """Build a unique id for a Google Drive indexing run."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    items_info = f"_{folder_count}f_{file_count}files"
    return f"drive_{connector_id}_{timestamp}{items_info}"


def progress(
    indexed_count: int,
    total_count: int | None = None,
    stage: str | None = None,
    stage_message: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Compute the progress message and metadata updates for an indexing run."""
    stage_messages = {
        "connecting": "Connecting to your account",
        "fetching": "Fetching your content",
        "processing": "Preparing for search",
        "storing": "Almost done",
    }

    if stage or stage_message:
        progress_msg = stage_message or stage_messages.get(stage, "Processing")
    else:
        # Legacy callers that pass neither stage nor message.
        progress_msg = "Fetching your content"

    metadata_updates: dict[str, Any] = {"indexed_count": indexed_count}
    if total_count is not None:
        metadata_updates["total_count"] = total_count
        progress_percent = int((indexed_count / total_count) * 100)
        metadata_updates["progress_percent"] = progress_percent
    if stage:
        metadata_updates["sync_stage"] = stage

    return progress_msg, metadata_updates


def retry(
    connector_name: str,
    indexed_count: int,
    retry_reason: str,
    attempt: int,
    max_attempts: int,
    wait_seconds: float | None = None,
    service_name: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Compute the retry message and metadata, framing the delay as the provider's."""
    if not service_name:
        service_name = connector_name
        # Strip the workspace suffix, e.g. "Notion - My Workspace" -> "Notion".
        if " - " in service_name:
            service_name = service_name.split(" - ")[0]

    # Worded so the delay reads as the provider's, not ours.
    retry_messages = {
        "rate_limit": f"{service_name} rate limit reached",
        "server_error": f"{service_name} is slow to respond",
        "timeout": f"{service_name} took too long",
        "temporary_error": f"{service_name} temporarily unavailable",
    }

    base_message = retry_messages.get(retry_reason, f"Waiting for {service_name}")

    # Only surface a wait time when it's long enough to be worth showing.
    if wait_seconds and wait_seconds > 5:
        message = f"{base_message}. Retrying in {int(wait_seconds)}s..."
    else:
        message = f"{base_message}. Retrying..."

    if indexed_count > 0:
        item_text = "item" if indexed_count == 1 else "items"
        message = f"{message} ({indexed_count} {item_text} synced so far)"

    metadata_updates = {
        "indexed_count": indexed_count,
        "sync_stage": "waiting_retry",
        "retry_attempt": attempt,
        "retry_max_attempts": max_attempts,
        "retry_reason": retry_reason,
        "retry_wait_seconds": wait_seconds,
    }

    return message, metadata_updates


def completion(
    connector_name: str,
    indexed_count: int,
    error_message: str | None = None,
    is_warning: bool = False,
    skipped_count: int | None = None,
    unsupported_count: int | None = None,
) -> tuple[str, str, str, dict[str, Any]]:
    """Compute the final title, message, status, and metadata for a finished run."""
    unsupported_text = ""
    if unsupported_count and unsupported_count > 0:
        file_word = "file was" if unsupported_count == 1 else "files were"
        unsupported_text = f" {unsupported_count} {file_word} not supported."

    if error_message:
        if indexed_count > 0:
            title = f"Ready: {connector_name}"
            file_text = "file" if indexed_count == 1 else "files"
            message = f"Now searchable! {indexed_count} {file_text} synced.{unsupported_text} Note: {error_message}"
            status = "completed"
        elif is_warning:
            title = f"Ready: {connector_name}"
            message = f"Sync complete.{unsupported_text} {error_message}"
            status = "completed"
        else:
            title = f"Failed: {connector_name}"
            message = f"Sync failed: {error_message}"
            if unsupported_text:
                message += unsupported_text
            status = "failed"
    else:
        title = f"Ready: {connector_name}"
        if indexed_count == 0:
            if unsupported_count and unsupported_count > 0:
                message = f"Sync complete.{unsupported_text}"
            else:
                message = "Already up to date!"
        else:
            file_text = "file" if indexed_count == 1 else "files"
            message = f"Now searchable! {indexed_count} {file_text} synced."
            if unsupported_text:
                message += unsupported_text
        status = "completed"

    metadata_updates = {
        "indexed_count": indexed_count,
        "skipped_count": skipped_count or 0,
        "unsupported_count": unsupported_count or 0,
        "sync_stage": "completed"
        if (not error_message or is_warning or indexed_count > 0)
        else "failed",
        "error_message": error_message,
    }

    return title, message, status, metadata_updates
