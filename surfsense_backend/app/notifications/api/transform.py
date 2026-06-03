"""Pure request/response helpers for the notifications API.

No DB or framework objects, so these are unit-testable in isolation.
"""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple

from app.notifications.api.schemas import NotificationResponse
from app.notifications.persistence import Notification


class SourceTypeFilter(NamedTuple):
    """The notification types and JSONB facet a source-type filter selects."""

    types: tuple[str, ...]
    metadata_key: str
    value: str


def parse_source_type(source_type: str) -> SourceTypeFilter | None:
    """Decode a `connector:<type>` / `doctype:<type>` filter, or None if unknown."""
    if source_type.startswith("connector:"):
        return SourceTypeFilter(
            types=("connector_indexing", "connector_deletion"),
            metadata_key="connector_type",
            value=source_type[len("connector:") :],
        )
    if source_type.startswith("doctype:"):
        return SourceTypeFilter(
            types=("document_processing",),
            metadata_key="document_type",
            value=source_type[len("doctype:") :],
        )
    return None


def parse_before_date(before_date: str) -> datetime:
    """Parse an ISO date for pagination; raises ValueError if malformed."""
    return datetime.fromisoformat(before_date.replace("Z", "+00:00"))


def to_response(notification: Notification) -> NotificationResponse:
    """Map a persisted notification to its API response shape."""
    return NotificationResponse(
        id=notification.id,
        user_id=str(notification.user_id),
        search_space_id=notification.search_space_id,
        type=notification.type,
        title=notification.title,
        message=notification.message,
        read=notification.read,
        metadata=notification.notification_metadata or {},
        created_at=notification.created_at.isoformat()
        if notification.created_at
        else "",
        updated_at=notification.updated_at.isoformat()
        if notification.updated_at
        else None,
    )
