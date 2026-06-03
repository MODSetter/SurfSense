"""Shared find/upsert/update logic for a single notification type."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.notifications.persistence import Notification

logger = logging.getLogger(__name__)


class BaseNotificationHandler:
    """Find, upsert, and update notifications of one ``type``."""

    def __init__(self, notification_type: str):
        self.notification_type = notification_type

    async def find_notification_by_operation(
        self,
        session: AsyncSession,
        user_id: UUID,
        operation_id: str,
        search_space_id: int | None = None,
    ) -> Notification | None:
        """Return the notification for ``operation_id``, if one exists."""
        query = select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == self.notification_type,
            Notification.notification_metadata["operation_id"].astext == operation_id,
        )
        if search_space_id is not None:
            query = query.where(Notification.search_space_id == search_space_id)

        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def find_or_create_notification(
        self,
        session: AsyncSession,
        user_id: UUID,
        operation_id: str,
        title: str,
        message: str,
        search_space_id: int | None = None,
        initial_metadata: dict[str, Any] | None = None,
    ) -> Notification:
        """Upsert a notification keyed by ``operation_id``."""
        notification = await self.find_notification_by_operation(
            session, user_id, operation_id, search_space_id
        )

        if notification:
            notification.title = title
            notification.message = message
            if initial_metadata:
                notification.notification_metadata = {
                    **notification.notification_metadata,
                    **initial_metadata,
                }
                # Tell SQLAlchemy the JSONB dict changed in place.
                flag_modified(notification, "notification_metadata")
            await session.commit()
            await session.refresh(notification)
            logger.info(
                f"Updated notification {notification.id} for operation {operation_id}"
            )
            return notification

        metadata = initial_metadata or {}
        metadata["operation_id"] = operation_id
        metadata["status"] = "in_progress"
        metadata["started_at"] = datetime.now(UTC).isoformat()

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
            f"Created notification {notification.id} for operation {operation_id}"
        )
        return notification

    async def update_notification(
        self,
        session: AsyncSession,
        notification: Notification,
        title: str | None = None,
        message: str | None = None,
        status: str | None = None,
        metadata_updates: dict[str, Any] | None = None,
    ) -> Notification:
        """Apply field/status/metadata changes and persist."""
        if title is not None:
            notification.title = title
        if message is not None:
            notification.message = message

        if status is not None:
            notification.notification_metadata["status"] = status
            if status in ("completed", "failed"):
                notification.notification_metadata["completed_at"] = datetime.now(
                    UTC
                ).isoformat()
            # Tell SQLAlchemy the JSONB dict changed in place.
            flag_modified(notification, "notification_metadata")

        if metadata_updates:
            notification.notification_metadata = {
                **notification.notification_metadata,
                **metadata_updates,
            }
            # Tell SQLAlchemy the JSONB dict changed in place.
            flag_modified(notification, "notification_metadata")

        await session.commit()
        await session.refresh(notification)
        logger.info(f"Updated notification {notification.id}")
        return notification
