"""Pure presentation logic for document-processing notifications."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from app.notifications.service.messages.text import format_title


def operation_id(document_type: str, filename: str, search_space_id: int) -> str:
    """Build a unique id for a document processing run."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    filename_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
    return f"doc_{document_type}_{search_space_id}_{timestamp}_{filename_hash}"


def started_title(document_name: str) -> str:
    """Title shown when document processing is queued."""
    return format_title("Processing: ", document_name)


def progress(
    stage: str,
    stage_message: str | None = None,
    chunks_count: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Compute the progress message and metadata updates for a processing run."""
    stage_messages = {
        "parsing": "Reading your file",
        "chunking": "Preparing for search",
        "embedding": "Preparing for search",
        "storing": "Finalizing",
    }

    message = stage_message or stage_messages.get(stage, "Processing")

    metadata_updates: dict[str, Any] = {"processing_stage": stage}
    if chunks_count is not None:
        metadata_updates["chunks_count"] = chunks_count

    return message, metadata_updates


def completion(
    document_name: str,
    error_message: str | None = None,
    document_id: int | None = None,
    chunks_count: int | None = None,
) -> tuple[str, str, str, dict[str, Any]]:
    """Compute the final title, message, status, and metadata for a finished run."""
    if error_message:
        title = format_title("Failed: ", document_name)
        message = f"Processing failed: {error_message}"
        status = "failed"
    else:
        title = format_title("Ready: ", document_name)
        message = "Now searchable!"
        status = "completed"

    metadata_updates: dict[str, Any] = {
        "processing_stage": "completed" if not error_message else "failed",
        "error_message": error_message,
    }
    if document_id is not None:
        metadata_updates["document_id"] = document_id
    if chunks_count is not None:
        metadata_updates["chunks_count"] = chunks_count

    return title, message, status, metadata_updates
