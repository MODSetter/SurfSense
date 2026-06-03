"""Notifications for replies to a user's comments."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.persistence import Notification
from app.notifications.service.base import BaseNotificationHandler
from app.notifications.service.messages.text import truncate

logger = logging.getLogger(__name__)


class CommentReplyNotificationHandler(BaseNotificationHandler):
    """Notifications for replies to a user's comments."""

    def __init__(self):
        super().__init__("comment_reply")

    async def find_notification_by_reply(
        self,
        session: AsyncSession,
        reply_id: int,
        user_id: UUID,
    ) -> Notification | None:
        query = select(Notification).where(
            Notification.type == self.notification_type,
            Notification.user_id == user_id,
            Notification.notification_metadata["reply_id"].astext == str(reply_id),
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def notify_comment_reply(
        self,
        session: AsyncSession,
        user_id: UUID,
        reply_id: int,
        parent_comment_id: int,
        message_id: int,
        thread_id: int,
        thread_title: str,
        author_id: str,
        author_name: str,
        author_avatar_url: str | None,
        author_email: str,
        content_preview: str,
        search_space_id: int,
    ) -> Notification:
        """Notify of a reply; idempotent on ``reply_id`` per user."""
        existing = await self.find_notification_by_reply(session, reply_id, user_id)
        if existing:
            logger.info(
                f"Notification already exists for reply {reply_id} to user {user_id}"
            )
            return existing

        title = f"{author_name} replied in a thread"
        message = truncate(content_preview, 100)

        metadata = {
            "reply_id": reply_id,
            "parent_comment_id": parent_comment_id,
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
                user_id=user_id,
                search_space_id=search_space_id,
                type=self.notification_type,
                title=title,
                message=message,
                notification_metadata=metadata,
            )
            session.add(notification)
            await session.commit()
            await session.refresh(notification)
            logger.info(
                f"Created comment_reply notification {notification.id} for user {user_id}"
            )
            return notification
        except Exception as e:
            await session.rollback()
            if (
                "duplicate key" in str(e).lower()
                or "unique constraint" in str(e).lower()
            ):
                logger.warning(
                    f"Duplicate notification for reply {reply_id} to user {user_id}"
                )
                existing = await self.find_notification_by_reply(
                    session, reply_id, user_id
                )
                if existing:
                    return existing
            raise
