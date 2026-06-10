"""Single entry point that composes the per-type notification handlers."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.persistence import Notification
from app.notifications.service.handlers import (
    AutoReloadFailedNotificationHandler,
    CommentReplyNotificationHandler,
    ConnectorIndexingNotificationHandler,
    DocumentProcessingNotificationHandler,
    InsufficientCreditsNotificationHandler,
    MentionNotificationHandler,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Facade over the per-type handlers; mutations sync via Zero."""

    connector_indexing = ConnectorIndexingNotificationHandler()
    document_processing = DocumentProcessingNotificationHandler()
    mention = MentionNotificationHandler()
    comment_reply = CommentReplyNotificationHandler()
    insufficient_credits = InsufficientCreditsNotificationHandler()
    auto_reload_failed = AutoReloadFailedNotificationHandler()

    @staticmethod
    async def create_notification(
        session: AsyncSession,
        user_id: UUID,
        notification_type: str,
        title: str,
        message: str,
        search_space_id: int | None = None,
        notification_metadata: dict[str, Any] | None = None,
    ) -> Notification:
        """Create a generic notification of any ``notification_type``."""
        notification = Notification(
            user_id=user_id,
            search_space_id=search_space_id,
            type=notification_type,
            title=title,
            message=message,
            notification_metadata=notification_metadata or {},
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        logger.info(f"Created notification {notification.id} for user {user_id}")
        return notification
