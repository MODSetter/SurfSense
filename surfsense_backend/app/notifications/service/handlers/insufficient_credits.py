"""Notifications for running out of credit during document processing."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.persistence import Notification
from app.notifications.service.base import BaseNotificationHandler
from app.notifications.service.messages import insufficient_credits as msg

logger = logging.getLogger(__name__)


class InsufficientCreditsNotificationHandler(BaseNotificationHandler):
    """Notifications for running out of credit during document processing."""

    def __init__(self):
        super().__init__("insufficient_credits")

    async def notify_insufficient_credits(
        self,
        session: AsyncSession,
        user_id: UUID,
        document_name: str,
        document_type: str,
        search_space_id: int,
        balance_micros: int,
        required_micros: int,
    ) -> Notification:
        """Notify that a document was blocked by insufficient credit."""
        operation_id = msg.operation_id(document_name, search_space_id)
        title, message = msg.summary(document_name, balance_micros, required_micros)

        metadata = {
            "operation_id": operation_id,
            "document_name": document_name,
            "document_type": document_type,
            "balance_micros": balance_micros,
            "required_micros": required_micros,
            "status": "failed",
            "error_type": "insufficient_credits",
            # Where the inbox item links to.
            "action_url": f"/dashboard/{search_space_id}/buy-more",
            "action_label": "Buy credits",
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
            f"Created insufficient_credits notification {notification.id} "
            f"for user {user_id}"
        )
        return notification
