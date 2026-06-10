"""The notification types the API recognizes."""

from __future__ import annotations

from typing import Literal

NotificationType = Literal[
    "connector_indexing",
    "connector_deletion",
    "document_processing",
    "new_mention",
    "comment_reply",
    "insufficient_credits",
    "auto_reload_failed",
]

NotificationCategory = Literal["comments", "status"]
