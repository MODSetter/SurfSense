"""Notifications for single-document processing."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.persistence import Notification
from app.notifications.service.base import BaseNotificationHandler


class DocumentProcessingNotificationHandler(BaseNotificationHandler):
    """Notifications for single-document processing."""

    def __init__(self):
        super().__init__("document_processing")

    def _generate_operation_id(
        self, document_type: str, filename: str, search_space_id: int
    ) -> str:
        """Build a unique id for a document processing run."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        # Create a short hash of filename to ensure uniqueness
        import hashlib

        filename_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
        return f"doc_{document_type}_{search_space_id}_{timestamp}_{filename_hash}"

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
        operation_id = self._generate_operation_id(
            document_type, document_name, search_space_id
        )
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
        stage_messages = {
            "parsing": "Reading your file",
            "chunking": "Preparing for search",
            "embedding": "Preparing for search",
            "storing": "Finalizing",
        }

        message = stage_message or stage_messages.get(stage, "Processing")

        metadata_updates = {"processing_stage": stage}
        # Store chunks_count in metadata for debugging, but don't show to user
        if chunks_count is not None:
            metadata_updates["chunks_count"] = chunks_count

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

        if error_message:
            title = f"Failed: {document_name}"
            message = f"Processing failed: {error_message}"
            status = "failed"
        else:
            title = f"Ready: {document_name}"
            message = "Now searchable!"
            status = "completed"

        metadata_updates = {
            "processing_stage": "completed" if not error_message else "failed",
            "error_message": error_message,
        }

        if document_id is not None:
            metadata_updates["document_id"] = document_id
        # Store chunks_count in metadata for debugging, but don't show to user
        if chunks_count is not None:
            metadata_updates["chunks_count"] = chunks_count

        return await self.update_notification(
            session=session,
            notification=notification,
            title=title,
            message=message,
            status=status,
            metadata_updates=metadata_updates,
        )
