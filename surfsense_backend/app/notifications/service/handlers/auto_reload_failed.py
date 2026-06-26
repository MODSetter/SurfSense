"""Notifications for failed off-session credit auto-reload charges."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.persistence import Notification
from app.notifications.service.base import BaseNotificationHandler
from app.notifications.service.messages import auto_reload_failed as msg

logger = logging.getLogger(__name__)


class AutoReloadFailedNotificationHandler(BaseNotificationHandler):
    """Notifications for declined auto-reload top-ups."""

    def __init__(self):
        super().__init__("auto_reload_failed")

    async def notify_auto_reload_failed(
        self,
        session: AsyncSession,
        user_id: UUID,
        amount_micros: int,
        payment_intent_id: str | None = None,
        reason: str | None = None,
    ) -> Notification:
        """Notify that an off-session auto-reload charge was declined.

        Not tied to a workspace (``workspace_id`` is None); the action
        links to the billing settings so the user can fix their card.
        """
        op_id = msg.operation_id(payment_intent_id or "")
        title, message = msg.summary(amount_micros, reason)

        return await self.find_or_create_notification(
            session=session,
            user_id=user_id,
            operation_id=op_id,
            title=title,
            message=message,
            workspace_id=None,
            initial_metadata={
                "amount_micros": amount_micros,
                "payment_intent_id": payment_intent_id,
                "status": "failed",
                "error_type": "auto_reload_failed",
                "action_url": "/dashboard",
                "action_label": "Update card",
            },
        )
