"""Pure metadata transitions for the notification lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def start_metadata(
    operation_id: str, initial_metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Seed metadata for a freshly opened, in-progress notification."""
    metadata = dict(initial_metadata or {})
    metadata["operation_id"] = operation_id
    metadata["status"] = "in_progress"
    metadata["started_at"] = datetime.now(UTC).isoformat()
    return metadata


def apply_update(
    current: dict[str, Any],
    status: str | None = None,
    metadata_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return metadata with the status/timestamp stamped and updates merged in."""
    metadata = dict(current)
    if status is not None:
        metadata["status"] = status
        if status in ("completed", "failed"):
            metadata["completed_at"] = datetime.now(UTC).isoformat()
    if metadata_updates:
        metadata = {**metadata, **metadata_updates}
    return metadata
