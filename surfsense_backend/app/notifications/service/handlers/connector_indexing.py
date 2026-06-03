"""Notifications for connector indexing runs."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.persistence import Notification
from app.notifications.service.base import BaseNotificationHandler


class ConnectorIndexingNotificationHandler(BaseNotificationHandler):
    """Notifications for connector indexing runs."""

    def __init__(self):
        super().__init__("connector_indexing")

    def _generate_operation_id(
        self,
        connector_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        """Build a unique id for a connector indexing run."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        date_range = ""
        if start_date or end_date:
            date_range = f"_{start_date or 'none'}_{end_date or 'none'}"
        return f"connector_{connector_id}_{timestamp}{date_range}"

    def _generate_google_drive_operation_id(
        self, connector_id: int, folder_count: int, file_count: int
    ) -> str:
        """Build a unique id for a Google Drive indexing run."""
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
        """Open (or refresh) the notification when indexing starts."""
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
        """Update the notification with indexing progress."""
        stage_messages = {
            "connecting": "Connecting to your account",
            "fetching": "Fetching your content",
            "processing": "Preparing for search",
            "storing": "Almost done",
        }

        if stage or stage_message:
            progress_msg = stage_message or stage_messages.get(stage, "Processing")
        else:
            # Legacy callers that pass neither stage nor message.
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
        """Surface that an external service is rate-limiting/retrying.

        Reusable by any connector; frames the delay as the provider's, not ours.
        """
        if not service_name:
            service_name = notification.notification_metadata.get(
                "connector_name", "Service"
            )
            # Strip the workspace suffix, e.g. "Notion - My Workspace" -> "Notion".
            if " - " in service_name:
                service_name = service_name.split(" - ")[0]

        # Worded so the delay reads as the provider's, not ours.
        retry_messages = {
            "rate_limit": f"{service_name} rate limit reached",
            "server_error": f"{service_name} is slow to respond",
            "timeout": f"{service_name} took too long",
            "temporary_error": f"{service_name} temporarily unavailable",
        }

        base_message = retry_messages.get(retry_reason, f"Waiting for {service_name}")

        # Only surface a wait time when it's long enough to be worth showing.
        if wait_seconds and wait_seconds > 5:
            message = f"{base_message}. Retrying in {int(wait_seconds)}s..."
        else:
            message = f"{base_message}. Retrying..."

        if indexed_count > 0:
            item_text = "item" if indexed_count == 1 else "items"
            message = f"{message} ({indexed_count} {item_text} synced so far)"

        metadata_updates = {
            "indexed_count": indexed_count,
            "sync_stage": "waiting_retry",
            "retry_attempt": attempt,
            "retry_max_attempts": max_attempts,
            "retry_reason": retry_reason,
            "retry_wait_seconds": wait_seconds,
        }

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

        unsupported_text = ""
        if unsupported_count and unsupported_count > 0:
            file_word = "file was" if unsupported_count == 1 else "files were"
            unsupported_text = f" {unsupported_count} {file_word} not supported."

        if error_message:
            if indexed_count > 0:
                title = f"Ready: {connector_name}"
                file_text = "file" if indexed_count == 1 else "files"
                message = f"Now searchable! {indexed_count} {file_text} synced.{unsupported_text} Note: {error_message}"
                status = "completed"
            elif is_warning:
                title = f"Ready: {connector_name}"
                message = f"Sync complete.{unsupported_text} {error_message}"
                status = "completed"
            else:
                title = f"Failed: {connector_name}"
                message = f"Sync failed: {error_message}"
                if unsupported_text:
                    message += unsupported_text
                status = "failed"
        else:
            title = f"Ready: {connector_name}"
            if indexed_count == 0:
                if unsupported_count and unsupported_count > 0:
                    message = f"Sync complete.{unsupported_text}"
                else:
                    message = "Already up to date!"
            else:
                file_text = "file" if indexed_count == 1 else "files"
                message = f"Now searchable! {indexed_count} {file_text} synced."
                if unsupported_text:
                    message += unsupported_text
            status = "completed"

        metadata_updates = {
            "indexed_count": indexed_count,
            "skipped_count": skipped_count or 0,
            "unsupported_count": unsupported_count or 0,
            "sync_stage": "completed"
            if (not error_message or is_warning or indexed_count > 0)
            else "failed",
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
        """Open (or refresh) the notification when Drive indexing starts."""
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
