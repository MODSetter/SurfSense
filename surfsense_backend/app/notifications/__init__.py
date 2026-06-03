"""User notifications: persistence, service, and HTTP API.

Emit notifications via :class:`~app.notifications.service.NotificationService`;
the router in :mod:`app.notifications.api` exposes the inbox endpoints.
"""

from __future__ import annotations

from app.notifications.persistence import Notification
from app.notifications.service import NotificationService

__all__ = [
    "Notification",
    "NotificationService",
]
