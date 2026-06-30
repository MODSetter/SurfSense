"""Notifications for connector indexing runs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.persistence import Notification
from app.notifications.service.base import BaseNotificationHandler
from app.notifications.service.messages import connector_indexing as msg


class ConnectorIndexingNotificationHandler(BaseNotificationHandler):
    """Notifications for connector indexing runs."""

    def __init__(self):
        super().__init__("connector_indexing")

    async def notify_indexing_started(
        self,
        session: AsyncSession,
        user_id: UUID,
        connector_id: int,
        connector_name: str,
        connector_type: str,
        workspace_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Notification:
        """Open (or refresh) the notification when indexing starts."""
        operation_id = msg.operation_id(connector_id, start_date, end_date)
        title = f"Syncing: {connector_name}"
        message = "Connecting to your account"

        metadata = {
            "connector_id": connector_id,
            "connector_name": connector_name,
            "connector_type": connector_type,
            "start_date": start_date,
            "end_date": end_date,
            "indexed_count": 0,
            "sync_stage": "connecting",
        }

        return await self.find_or_create_notification(
            session=session,
            user_id=user_id,
            operation_id=operation_id,
            title=title,
            message=message,
            workspace_id=workspace_id,
            initial_metadata=metadata,
        )

    async def notify_indexing_progress(
        self,
        session: AsyncSession,
        notification: Notification,
        indexed_count: int,
        total_count: int | None = None,
        stage: str | None = None,
        stage_message: str | None = None,
    ) -> Notification:
        """Update the notification with indexing progress."""
        message, metadata_updates = msg.progress(
            indexed_count, total_count, stage, stage_message
        )
        return await self.update_notification(
            session=session,
            notification=notification,
            message=message,
            status="in_progress",
            metadata_updates=metadata_updates,
        )

    async def notify_retry_progress(
        self,
        session: AsyncSession,
        notification: Notification,
        indexed_count: int,
        retry_reason: str,
        attempt: int,
        max_attempts: int,
        wait_seconds: float | None = None,
        service_name: str | None = None,
    ) -> Notification:
        """Surface that an external service is rate-limiting/retrying."""
        connector_name = notification.notification_metadata.get(
            "connector_name", "Service"
        )
        message, metadata_updates = msg.retry(
            connector_name,
            indexed_count,
            retry_reason,
            attempt,
            max_attempts,
            wait_seconds,
            service_name,
        )
        return await self.update_notification(
            session=session,
            notification=notification,
            message=message,
            status="in_progress",
            metadata_updates=metadata_updates,
        )

    async def notify_indexing_completed(
        self,
        session: AsyncSession,
        notification: Notification,
        indexed_count: int,
        error_message: str | None = None,
        is_warning: bool = False,
        skipped_count: int | None = None,
        unsupported_count: int | None = None,
    ) -> Notification:
        """Finalize the notification as ready/failed when indexing ends."""
        connector_name = notification.notification_metadata.get(
            "connector_name", "Connector"
        )
        title, message, status, metadata_updates = msg.completion(
            connector_name,
            indexed_count,
            error_message,
            is_warning,
            skipped_count,
            unsupported_count,
        )
        return await self.update_notification(
            session=session,
            notification=notification,
            title=title,
            message=message,
            status=status,
            metadata_updates=metadata_updates,
        )

    async def notify_google_drive_indexing_started(
        self,
        session: AsyncSession,
        user_id: UUID,
        connector_id: int,
        connector_name: str,
        connector_type: str,
        workspace_id: int,
        folder_count: int,
        file_count: int,
        folder_names: list[str] | None = None,
        file_names: list[str] | None = None,
    ) -> Notification:
        """Open (or refresh) the notification when Drive indexing starts."""
        operation_id = msg.google_drive_operation_id(
            connector_id, folder_count, file_count
        )
        title = f"Syncing: {connector_name}"
        message = "Preparing your files"

        metadata = {
            "connector_id": connector_id,
            "connector_name": connector_name,
            "connector_type": connector_type,
            "folder_count": folder_count,
            "file_count": file_count,
            "indexed_count": 0,
            "sync_stage": "connecting",
        }

        if folder_names:
            metadata["folder_names"] = folder_names
        if file_names:
            metadata["file_names"] = file_names

        return await self.find_or_create_notification(
            session=session,
            user_id=user_id,
            operation_id=operation_id,
            title=title,
            message=message,
            workspace_id=workspace_id,
            initial_metadata=metadata,
        )
