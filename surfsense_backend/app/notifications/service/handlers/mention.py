"""Notifications for @mentions in comments."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.persistence import Notification
from app.notifications.service.base import BaseNotificationHandler
from app.notifications.service.messages.text import truncate

logger = logging.getLogger(__name__)


class MentionNotificationHandler(BaseNotificationHandler):
    """Notifications for @mentions in comments."""

    def __init__(self):
        super().__init__("new_mention")

    async def find_notification_by_mention(
        self,
        session: AsyncSession,
        mention_id: int,
    ) -> Notification | None:
        """Return the notification for ``mention_id``, if one exists."""
        query = select(Notification).where(
            Notification.type == self.notification_type,
            Notification.notification_metadata["mention_id"].astext == str(mention_id),
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def notify_new_mention(
        self,
        session: AsyncSession,
        mentioned_user_id: UUID,
        mention_id: int,
        comment_id: int,
        message_id: int,
        thread_id: int,
        thread_title: str,
        author_id: str,
        author_name: str,
        author_avatar_url: str | None,
        author_email: str,
        content_preview: str,
        workspace_id: int,
    ) -> Notification:
        """Notify a mentioned user; idempotent on ``mention_id``."""
        existing = await self.find_notification_by_mention(session, mention_id)
        if existing:
            logger.info(
                f"Notification already exists for mention {mention_id}, returning existing"
            )
            return existing

        title = f"{author_name} mentioned you"
        message = truncate(content_preview, 100)

        metadata = {
            "mention_id": mention_id,
            "comment_id": comment_id,
            "message_id": message_id,
            "thread_id": thread_id,
            "thread_title": thread_title,
            "author_id": author_id,
            "author_name": author_name,
            "author_avatar_url": author_avatar_url,
            "author_email": author_email,
            "content_preview": content_preview[:200],
        }

        try:
            notification = Notification(
                user_id=mentioned_user_id,
                workspace_id=workspace_id,
                type=self.notification_type,
                title=title,
                message=message,
                notification_metadata=metadata,
            )
            session.add(notification)
            await session.commit()
            await session.refresh(notification)
            logger.info(
                f"Created new_mention notification {notification.id} for user {mentioned_user_id}"
            )
            return notification
        except Exception as e:
            # Race: a concurrent insert won; fetch the existing row instead.
            await session.rollback()
            if (
                "duplicate key" in str(e).lower()
                or "unique constraint" in str(e).lower()
            ):
                logger.warning(
                    f"Duplicate notification detected for mention {mention_id}, fetching existing"
                )
                existing = await self.find_notification_by_mention(session, mention_id)
                if existing:
                    return existing
            raise
