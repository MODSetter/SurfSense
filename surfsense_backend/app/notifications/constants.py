"""Notification policy constants."""

from __future__ import annotations

# Matches notifications.title VARCHAR(200).
TITLE_MAX_LENGTH = 200

# Notifications newer than this are live-synced; older ones load via the list endpoint.
SYNC_WINDOW_DAYS = 14

# Maps an inbox tab to the notification types it shows.
CATEGORY_TYPES: dict[str, tuple[str, ...]] = {
    "comments": ("new_mention", "comment_reply"),
    "status": (
        "connector_indexing",
        "connector_deletion",
        "document_processing",
        "insufficient_credits",
        "auto_reload_failed",
    ),
}
