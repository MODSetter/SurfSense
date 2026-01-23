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
            logger.info(
                f"Updated notification {notification.id} for operation {operation_id}"
            )
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
                notification.notification_metadata["completed_at"] = datetime.now(
                    UTC
                ).isoformat()
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
        self,
        connector_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
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

    def _generate_google_drive_operation_id(
        self, connector_id: int, folder_count: int, file_count: int
    ) -> str:
        """
        Generate a unique operation ID for a Google Drive indexing operation.

        Args:
            connector_id: Connector ID
            folder_count: Number of folders to index
            file_count: Number of files to index

        Returns:
            Unique operation ID string
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        items_info = f"_{folder_count}f_{file_count}files"
        return f"drive_{connector_id}_{timestamp}{items_info}"

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
            search_space_id=search_space_id,
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
        """
        Update notification with indexing progress.

        Args:
            session: Database session
            notification: Notification to update
            indexed_count: Number of items indexed so far
            total_count: Total number of items (optional)
            stage: Current sync stage (fetching, processing, storing) (optional)
            stage_message: Optional custom message for the stage

        Returns:
            Updated notification
        """
        # User-friendly stage messages (clean, no ellipsis - spinner shows activity)
        stage_messages = {
            "connecting": "Connecting to your account",
            "fetching": "Fetching your content",
            "processing": "Preparing for search",
            "storing": "Almost done",
        }

        # Use stage-based message if stage provided, otherwise fallback
        if stage or stage_message:
            progress_msg = stage_message or stage_messages.get(stage, "Processing")
        else:
            # Fallback for backward compatibility
            progress_msg = "Fetching your content"

        metadata_updates = {"indexed_count": indexed_count}
        if total_count is not None:
            metadata_updates["total_count"] = total_count
            progress_percent = int((indexed_count / total_count) * 100)
            metadata_updates["progress_percent"] = progress_percent
        if stage:
            metadata_updates["sync_stage"] = stage

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
        connector_name = notification.notification_metadata.get(
            "connector_name", "Connector"
        )

        if error_message:
            title = f"Failed: {connector_name}"
            message = f"Sync failed: {error_message}"
            status = "failed"
        else:
            title = f"Ready: {connector_name}"
            if indexed_count == 0:
                message = "Already up to date! No new items to sync."
            else:
                item_text = "item" if indexed_count == 1 else "items"
                message = f"Now searchable! {indexed_count} {item_text} synced."
            status = "completed"

        metadata_updates = {
            "indexed_count": indexed_count,
            "sync_stage": "completed" if not error_message else "failed",
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

    async def notify_google_drive_indexing_started(
        self,
        session: AsyncSession,
        user_id: UUID,
        connector_id: int,
        connector_name: str,
        connector_type: str,
        search_space_id: int,
        folder_count: int,
        file_count: int,
        folder_names: list[str] | None = None,
        file_names: list[str] | None = None,
    ) -> Notification:
        """
        Create or update notification when Google Drive indexing starts.

        Args:
            session: Database session
            user_id: User ID
            connector_id: Connector ID
            connector_name: Connector name
            connector_type: Connector type
            search_space_id: Search space ID
            folder_count: Number of folders to index
            file_count: Number of files to index
            folder_names: List of folder names (optional)
            file_names: List of file names (optional)

        Returns:
            Notification: The created or updated notification
        """
        operation_id = self._generate_google_drive_operation_id(
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
            search_space_id=search_space_id,
            initial_metadata=metadata,
        )


class DocumentProcessingNotificationHandler(BaseNotificationHandler):
    """Handler for document processing notifications."""

    def __init__(self):
        super().__init__("document_processing")

    def _generate_operation_id(
        self, document_type: str, filename: str, search_space_id: int
    ) -> str:
        """
        Generate a unique operation ID for a document processing operation.

        Args:
            document_type: Type of document (FILE, YOUTUBE_VIDEO, CRAWLED_URL, etc.)
            filename: Name of the file/document
            search_space_id: Search space ID

        Returns:
            Unique operation ID string
        """
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
        """
        Create notification when document processing starts.

        Args:
            session: Database session
            user_id: User ID
            document_type: Type of document (FILE, YOUTUBE_VIDEO, CRAWLED_URL, etc.)
            document_name: Name/title of the document
            search_space_id: Search space ID
            file_size: Size of file in bytes (optional)

        Returns:
            Notification: The created notification
        """
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
        """
        Update notification with processing progress.

        Args:
            session: Database session
            notification: Notification to update
            stage: Current processing stage (parsing, chunking, embedding, storing)
            stage_message: Optional custom message for the stage
            chunks_count: Number of chunks created (optional, stored in metadata only)

        Returns:
            Updated notification
        """
        # User-friendly stage messages
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
        """
        Update notification when document processing completes.

        Args:
            session: Database session
            notification: Notification to update
            document_id: ID of the created document (optional)
            chunks_count: Total number of chunks created (optional)
            error_message: Error message if processing failed (optional)

        Returns:
            Updated notification
        """
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


class MentionNotificationHandler(BaseNotificationHandler):
    """Handler for new mention notifications."""

    def __init__(self):
        super().__init__("new_mention")

    async def find_notification_by_mention(
        self,
        session: AsyncSession,
        mention_id: int,
    ) -> Notification | None:
        """
        Find an existing notification by mention ID.

        Args:
            session: Database session
            mention_id: The mention ID to search for

        Returns:
            Notification if found, None otherwise
        """
        query = select(Notification).where(
            Notification.type == self.notification_type,
            Notification.notification_metadata["mention_id"].astext == str(mention_id),
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def notify_new_mention(
        self,
        session: AsyncSession,
        mentioned_user_id: UUID,
        mention_id: int,
        comment_id: int,
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
        """
        Create notification when a user is @mentioned in a comment.
        Uses mention_id for idempotency to prevent duplicate notifications.

        Args:
            session: Database session
            mentioned_user_id: User who was mentioned
            mention_id: ID of the mention record (used for idempotency)
            comment_id: ID of the comment containing the mention
            message_id: ID of the message being commented on
            thread_id: ID of the chat thread
            thread_title: Title of the chat thread
            author_id: ID of the comment author
            author_name: Display name of the comment author
            author_avatar_url: Avatar URL of the comment author
            author_email: Email of the comment author (for fallback initials)
            content_preview: First ~100 chars of the comment
            search_space_id: Search space ID

        Returns:
            Notification: The created or existing notification
        """
        # Check if notification already exists for this mention (idempotency)
        existing = await self.find_notification_by_mention(session, mention_id)
        if existing:
            logger.info(
                f"Notification already exists for mention {mention_id}, returning existing"
            )
            return existing

        title = f"{author_name} mentioned you"
        message = content_preview[:100] + ("..." if len(content_preview) > 100 else "")

        metadata = {
            "mention_id": mention_id,
            "comment_id": comment_id,
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
                user_id=mentioned_user_id,
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
                f"Created new_mention notification {notification.id} for user {mentioned_user_id}"
            )
            return notification
        except Exception as e:
            # Handle race condition - if duplicate key error, try to fetch existing
            await session.rollback()
            if (
                "duplicate key" in str(e).lower()
                or "unique constraint" in str(e).lower()
            ):
                logger.warning(
                    f"Duplicate notification detected for mention {mention_id}, fetching existing"
                )
                existing = await self.find_notification_by_mention(session, mention_id)
                if existing:
                    return existing
            # Re-raise if not a duplicate key error or couldn't find existing
            raise


class NotificationService:
    """Service for creating and managing notifications that sync via Electric SQL."""

    # Handler instances
    connector_indexing = ConnectorIndexingNotificationHandler()
    document_processing = DocumentProcessingNotificationHandler()
    mention = MentionNotificationHandler()

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
            notification_type: Type of notification (e.g., 'document_processing', 'connector_indexing')
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
