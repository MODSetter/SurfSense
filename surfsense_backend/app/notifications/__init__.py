"""User notifications: persistence, service, and HTTP API.

Emit notifications via :class:`~app.notifications.service.NotificationService`;
the router in :mod:`app.notifications.api` exposes the inbox endpoints.
"""

from __future__ import annotations

# Initialize app.db first to avoid a partial-init circular import when this
# package is the entry point (e.g. Celery loading it before any ORM code).
import app.db  # noqa: F401
from app.notifications.persistence import Notification
from app.notifications.service import NotificationService

__all__ = [
    "Notification",
    "NotificationService",
]
