"""Service for creating and managing notifications with Electric SQL sync."""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db import Notification

logger = logging.getLogger(__name__)


class BaseNotificationHandler:
    """Base class for notification handlers - provides common functionality."""

    def __init__(self, notification_type: str):
        """
        Initialize the notification handler.

        Args:
            notification_type: Type of notification (e.g., 'connector_indexing', 'document_processing')
        """
        self.notification_type = notification_type

    async def find_notification_by_operation(
        self,
        session: AsyncSession,
        user_id: UUID,
        operation_id: str,
        search_space_id: int | None = None,
    ) -> Notification | None:
        """
        Find an existing notification by operation ID.

        Args:
            session: Database session
            user_id: User ID
            operation_id: Unique operation identifier
            search_space_id: Optional search space ID

        Returns:
            Notification if found, None otherwise
        """
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
        """
        Find an existing notification or create a new one.

        Args:
            session: Database session
            user_id: User ID
            operation_id: Unique operation identifier
            title: Notification title
            message: Notification message
            search_space_id: Optional search space ID
            initial_metadata: Initial metadata dictionary

        Returns:
            Notification: The found or created notification
        """
        # Try to find existing notification
        notification = await self.find_notification_by_operation(
            session, user_id, operation_id, search_space_id
        )

        if notification:
            # Update existing notification
            notification.title = title
            notification.message = message
            if initial_metadata:
                notification.notification_metadata = {
                    **notification.notification_metadata,
                    **initial_metadata,
                }
                # Mark JSONB column as modified so SQLAlchemy detects the change
                flag_modified(notification, "notification_metadata")
            await session.commit()
            await session.refresh(notification)
            logger.info(f"Updated notification {notification.id} for operation {operation_id}")
            return notification

        # Create new notification
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
        logger.info(f"Created notification {notification.id} for operation {operation_id}")
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
        """
        Update an existing notification.

        Args:
            session: Database session
            notification: Notification to update
            title: New title (optional)
            message: New message (optional)
            status: New status (optional)
            metadata_updates: Additional metadata to merge (optional)

        Returns:
            Updated notification
        """
        if title is not None:
            notification.title = title
        if message is not None:
            notification.message = message

        if status is not None:
            notification.notification_metadata["status"] = status
            if status in ("completed", "failed"):
                notification.notification_metadata["completed_at"] = (
                    datetime.now(UTC).isoformat()
                )
            # Mark JSONB column as modified so SQLAlchemy detects the change
            flag_modified(notification, "notification_metadata")

        if metadata_updates:
            notification.notification_metadata = {
                **notification.notification_metadata,
                **metadata_updates,
            }
            # Mark JSONB column as modified
            flag_modified(notification, "notification_metadata")

        await session.commit()
        await session.refresh(notification)
        logger.info(f"Updated notification {notification.id}")
        return notification


class ConnectorIndexingNotificationHandler(BaseNotificationHandler):
    """Handler for connector indexing notifications."""

    def __init__(self):
        super().__init__("connector_indexing")

    def _generate_operation_id(
        self, connector_id: int, start_date: str | None = None, end_date: str | None = None
    ) -> str:
        """
        Generate a unique operation ID for a connector indexing operation.

        Args:
            connector_id: Connector ID
            start_date: Start date (optional)
            end_date: End date (optional)

        Returns:
            Unique operation ID string
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        date_range = ""
        if start_date or end_date:
            date_range = f"_{start_date or 'none'}_{end_date or 'none'}"
        return f"connector_{connector_id}_{timestamp}{date_range}"

    async def notify_indexing_started(
        self,
        session: AsyncSession,
        user_id: UUID,
        connector_id: int,
        connector_name: str,
        connector_type: str,
        search_space_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Notification:
        """
        Create or update notification when connector indexing starts.

        Args:
            session: Database session
            user_id: User ID
            connector_id: Connector ID
            connector_name: Connector name
            connector_type: Connector type
            search_space_id: Search space ID
            start_date: Start date for indexing
            end_date: End date for indexing

        Returns:
            Notification: The created or updated notification
        """
        operation_id = self._generate_operation_id(connector_id, start_date, end_date)
        title = f"Indexing: {connector_name}"
        message = f'Indexing "{connector_name}" in progress...'

        metadata = {
            "connector_id": connector_id,
            "connector_name": connector_name,
            "connector_type": connector_type,
            "start_date": start_date,
            "end_date": end_date,
            "indexed_count": 0,
        }

        return await self.find_or_create_notification(
            session=session,
            user_id=user_id,
            operation_id=operation_id,
            title=title,
            message=message,
            search_space_id=search_space_id,
            initial_metadata=metadata,
        )

    async def notify_indexing_progress(
        self,
        session: AsyncSession,
        notification: Notification,
        indexed_count: int,
        total_count: int | None = None,
    ) -> Notification:
        """
        Update notification with indexing progress.

        Args:
            session: Database session
            notification: Notification to update
            indexed_count: Number of items indexed so far
            total_count: Total number of items (optional)

        Returns:
            Updated notification
        """
        connector_name = notification.notification_metadata.get("connector_name", "Connector")
        progress_msg = f'Indexing "{connector_name}": {indexed_count} items'
        if total_count is not None:
            progress_msg += f" of {total_count}"
        progress_msg += " indexed..."

        metadata_updates = {"indexed_count": indexed_count}
        if total_count is not None:
            metadata_updates["total_count"] = total_count
            progress_percent = int((indexed_count / total_count) * 100)
            metadata_updates["progress_percent"] = progress_percent

        return await self.update_notification(
            session=session,
            notification=notification,
            message=progress_msg,
            status="in_progress",
            metadata_updates=metadata_updates,
        )

    async def notify_indexing_completed(
        self,
        session: AsyncSession,
        notification: Notification,
        indexed_count: int,
        error_message: str | None = None,
    ) -> Notification:
        """
        Update notification when connector indexing completes.

        Args:
            session: Database session
            notification: Notification to update
            indexed_count: Total number of items indexed
            error_message: Error message if indexing failed (optional)

        Returns:
            Updated notification
        """
        connector_name = notification.notification_metadata.get("connector_name", "Connector")

        if error_message:
            title = f"Indexing failed: {connector_name}"
            message = f'Indexing "{connector_name}" failed: {error_message}'
            status = "failed"
        else:
            title = f"Indexing completed: {connector_name}"
            message = f'Indexing "{connector_name}" completed successfully. {indexed_count} items indexed.'
            status = "completed"

        metadata_updates = {
            "indexed_count": indexed_count,
            "error_message": error_message,
        }

        return await self.update_notification(
            session=session,
            notification=notification,
            title=title,
            message=message,
            status=status,
            metadata_updates=metadata_updates,
        )


class NotificationService:
    """Service for creating and managing notifications that sync via Electric SQL."""

    # Handler instances
    connector_indexing = ConnectorIndexingNotificationHandler()

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
        """
        Create a notification - Electric SQL will automatically sync it to frontend.

        Args:
            session: Database session
            user_id: User to notify
            notification_type: Type of notification (e.g., 'document_processed', 'connector_indexed')
            title: Notification title
            message: Notification message
            search_space_id: Optional search space ID
            notification_metadata: Optional metadata dictionary

        Returns:
            Notification: The created notification
        """
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

    @staticmethod
    async def create_document_processed_notification(
        session: AsyncSession,
        user_id: UUID,
        document_id: int,
        document_title: str,
        status: str,
        search_space_id: int,
    ) -> Notification:
        """
        Create notification when document processing completes.

        Args:
            session: Database session
            user_id: User to notify
            document_id: ID of the processed document
            document_title: Title of the document
            status: Processing status ('SUCCESS', 'FAILED')
            search_space_id: Search space ID

        Returns:
            Notification: The created notification
        """
        status_lower = status.lower()
        title = f"Document processed: {document_title}"
        message = f'Your document "{document_title}" has been {status_lower}.'

        return await NotificationService.create_notification(
            session=session,
            user_id=user_id,
            notification_type="document_processed",
            title=title,
            message=message,
            search_space_id=search_space_id,
            notification_metadata={
                "document_id": document_id,
                "status": status,
            },
        )

    @staticmethod
    async def create_connector_indexed_notification(
        session: AsyncSession,
        user_id: UUID,
        connector_name: str,
        connector_type: str,
        status: str,
        search_space_id: int,
        indexed_count: int | None = None,
    ) -> Notification:
        """
        Create notification when connector indexing completes.
        DEPRECATED: Use NotificationService.connector_indexing methods instead.

        Args:
            session: Database session
            user_id: User to notify
            connector_name: Name of the connector
            connector_type: Type of connector
            status: Indexing status ('SUCCESS', 'FAILED')
            search_space_id: Search space ID
            indexed_count: Number of items indexed (optional)

        Returns:
            Notification: The created notification
        """
        status_lower = status.lower()
        title = f"Connector indexed: {connector_name}"
        message = f'Your connector "{connector_name}" has finished indexing ({status_lower}).'
        if indexed_count is not None:
            message += f" {indexed_count} items indexed."

        return await NotificationService.create_notification(
            session=session,
            user_id=user_id,
            notification_type="connector_indexed",
            title=title,
            message=message,
            search_space_id=search_space_id,
            notification_metadata={
                "connector_name": connector_name,
                "connector_type": connector_type,
                "status": status,
                "indexed_count": indexed_count,
            },
        )
