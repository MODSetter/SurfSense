"""Service for creating and managing notifications."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for creating notifications that sync via Electric SQL."""

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
