"""Notifications for exceeding the page limit."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.persistence import Notification
from app.notifications.service.base import BaseNotificationHandler
from app.notifications.service.messages import page_limit as msg

logger = logging.getLogger(__name__)


class PageLimitNotificationHandler(BaseNotificationHandler):
    """Notifications for exceeding the page limit."""

    def __init__(self):
        super().__init__("page_limit_exceeded")

    async def notify_page_limit_exceeded(
        self,
        session: AsyncSession,
        user_id: UUID,
        document_name: str,
        document_type: str,
        search_space_id: int,
        pages_used: int,
        pages_limit: int,
        pages_to_add: int,
    ) -> Notification:
        """Notify that a document was blocked by the page limit."""
        operation_id = msg.operation_id(document_name, search_space_id)
        title, message = msg.summary(
            document_name, pages_used, pages_limit, pages_to_add
        )

        metadata = {
            "operation_id": operation_id,
            "document_name": document_name,
            "document_type": document_type,
            "pages_used": pages_used,
            "pages_limit": pages_limit,
            "pages_to_add": pages_to_add,
            "status": "failed",
            "error_type": "page_limit_exceeded",
            # Where the inbox item links to.
            "action_url": f"/dashboard/{search_space_id}/more-pages",
            "action_label": "Upgrade Plan",
        }

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
            f"Created page_limit_exceeded notification {notification.id} for user {user_id}"
        )
        return notification
