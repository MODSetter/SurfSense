"""Notifications for single-document processing."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.persistence import Notification
from app.notifications.service.base import BaseNotificationHandler
from app.notifications.service.messages import document_processing as msg


class DocumentProcessingNotificationHandler(BaseNotificationHandler):
    """Notifications for single-document processing."""

    def __init__(self):
        super().__init__("document_processing")

    async def notify_processing_started(
        self,
        session: AsyncSession,
        user_id: UUID,
        document_type: str,
        document_name: str,
        search_space_id: int,
        file_size: int | None = None,
    ) -> Notification:
        """Open the notification when document processing is queued."""
        operation_id = msg.operation_id(document_type, document_name, search_space_id)
        title = f"Processing: {document_name}"
        message = "Waiting in queue"

        metadata = {
            "document_type": document_type,
            "document_name": document_name,
            "processing_stage": "queued",
        }

        if file_size is not None:
            metadata["file_size"] = file_size

        return await self.find_or_create_notification(
            session=session,
            user_id=user_id,
            operation_id=operation_id,
            title=title,
            message=message,
            search_space_id=search_space_id,
            initial_metadata=metadata,
        )

    async def notify_processing_progress(
        self,
        session: AsyncSession,
        notification: Notification,
        stage: str,
        stage_message: str | None = None,
        chunks_count: int | None = None,
    ) -> Notification:
        """Update the notification with the current processing stage."""
        message, metadata_updates = msg.progress(stage, stage_message, chunks_count)

        return await self.update_notification(
            session=session,
            notification=notification,
            message=message,
            status="in_progress",
            metadata_updates=metadata_updates,
        )

    async def notify_processing_completed(
        self,
        session: AsyncSession,
        notification: Notification,
        document_id: int | None = None,
        chunks_count: int | None = None,
        error_message: str | None = None,
    ) -> Notification:
        """Finalize the notification as ready/failed when processing ends."""
        document_name = notification.notification_metadata.get(
            "document_name", "Document"
        )
        title, message, status, metadata_updates = msg.completion(
            document_name, error_message, document_id, chunks_count
        )

        return await self.update_notification(
            session=session,
            notification=notification,
            title=title,
            message=message,
            status=status,
            metadata_updates=metadata_updates,
        )
