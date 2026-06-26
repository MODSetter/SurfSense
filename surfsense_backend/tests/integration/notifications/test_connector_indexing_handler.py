"""Behavior guard for the connector-indexing notification handler.

Exercises the real handler against Postgres via the transactional db_session,
pinning the title/message/status/metadata it produces so the upcoming
functional-core extraction cannot drift.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Workspace, User
from app.notifications.service import NotificationService

pytestmark = pytest.mark.integration


async def test_indexing_started_opens_notification(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """Starting indexing opens an unread notification with connecting-stage metadata."""
    notification = await NotificationService.connector_indexing.notify_indexing_started(
        session=db_session,
        user_id=db_user.id,
        connector_id=42,
        connector_name="Notion - My Workspace",
        connector_type="NOTION_CONNECTOR",
        workspace_id=db_workspace.id,
    )

    assert notification.id is not None
    assert notification.type == "connector_indexing"
    assert notification.title == "Syncing: Notion - My Workspace"
    assert notification.message == "Connecting to your account"
    assert notification.read is False

    metadata = notification.notification_metadata
    assert metadata["connector_id"] == 42
    assert metadata["connector_type"] == "NOTION_CONNECTOR"
    assert metadata["indexed_count"] == 0
    assert metadata["sync_stage"] == "connecting"
    assert metadata["status"] == "in_progress"
    assert "operation_id" in metadata
    assert "started_at" in metadata


async def _started(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    *,
    connector_name: str = "Notion - My Workspace",
):
    """Open a connector-indexing notification to update in the tests below."""
    return await NotificationService.connector_indexing.notify_indexing_started(
        session=db_session,
        user_id=db_user.id,
        connector_id=42,
        connector_name=connector_name,
        connector_type="NOTION_CONNECTOR",
        workspace_id=db_workspace.id,
    )


async def test_indexing_progress_reports_stage_and_percent(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """Progress updates surface the stage message and compute a percent complete."""
    notification = await _started(db_session, db_user, db_workspace)

    updated = await NotificationService.connector_indexing.notify_indexing_progress(
        session=db_session,
        notification=notification,
        indexed_count=5,
        total_count=10,
        stage="fetching",
    )

    assert updated.message == "Fetching your content"
    metadata = updated.notification_metadata
    assert metadata["indexed_count"] == 5
    assert metadata["total_count"] == 10
    assert metadata["progress_percent"] == 50
    assert metadata["sync_stage"] == "fetching"
    assert metadata["status"] == "in_progress"


async def test_indexing_completed_clean_success(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """A clean multi-file sync reports ready/completed with plural wording."""
    notification = await _started(db_session, db_user, db_workspace)

    done = await NotificationService.connector_indexing.notify_indexing_completed(
        session=db_session,
        notification=notification,
        indexed_count=3,
    )

    assert done.title == "Ready: Notion - My Workspace"
    assert done.message == "Now searchable! 3 files synced."
    assert done.notification_metadata["status"] == "completed"
    assert done.notification_metadata["sync_stage"] == "completed"


async def test_indexing_completed_singular_file(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """A single synced file uses singular 'file' wording."""
    notification = await _started(db_session, db_user, db_workspace)

    done = await NotificationService.connector_indexing.notify_indexing_completed(
        session=db_session,
        notification=notification,
        indexed_count=1,
    )

    assert done.message == "Now searchable! 1 file synced."


async def test_indexing_completed_nothing_to_sync(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """Completing with nothing new reports 'Already up to date!'."""
    notification = await _started(db_session, db_user, db_workspace)

    done = await NotificationService.connector_indexing.notify_indexing_completed(
        session=db_session,
        notification=notification,
        indexed_count=0,
    )

    assert done.title == "Ready: Notion - My Workspace"
    assert done.message == "Already up to date!"
    assert done.notification_metadata["status"] == "completed"


async def test_indexing_completed_hard_failure(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """An error with nothing synced reports a hard failure."""
    notification = await _started(db_session, db_user, db_workspace)

    done = await NotificationService.connector_indexing.notify_indexing_completed(
        session=db_session,
        notification=notification,
        indexed_count=0,
        error_message="boom",
    )

    assert done.title == "Failed: Notion - My Workspace"
    assert done.message == "Sync failed: boom"
    assert done.notification_metadata["status"] == "failed"
    assert done.notification_metadata["sync_stage"] == "failed"


async def test_indexing_completed_partial_with_error_note(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """An error after partial progress still completes, with an appended note."""
    notification = await _started(db_session, db_user, db_workspace)

    done = await NotificationService.connector_indexing.notify_indexing_completed(
        session=db_session,
        notification=notification,
        indexed_count=2,
        error_message="partial outage",
    )

    assert done.title == "Ready: Notion - My Workspace"
    assert done.message == "Now searchable! 2 files synced. Note: partial outage"
    assert done.notification_metadata["status"] == "completed"


async def test_retry_progress_frames_delay_as_providers(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """A retry message frames the delay as the provider's, using its short name."""
    notification = await _started(db_session, db_user, db_workspace)

    retry = await NotificationService.connector_indexing.notify_retry_progress(
        session=db_session,
        notification=notification,
        indexed_count=0,
        retry_reason="rate_limit",
        attempt=1,
        max_attempts=3,
    )

    # service_name is derived from the connector name, stripping the workspace suffix.
    assert retry.message == "Notion rate limit reached. Retrying..."
    assert retry.notification_metadata["sync_stage"] == "waiting_retry"
    assert retry.notification_metadata["retry_attempt"] == 1
    assert retry.notification_metadata["retry_reason"] == "rate_limit"


async def test_retry_progress_shows_wait_and_synced_count(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """A retry surfaces the wait time and how many items synced so far."""
    notification = await _started(db_session, db_user, db_workspace)

    retry = await NotificationService.connector_indexing.notify_retry_progress(
        session=db_session,
        notification=notification,
        indexed_count=2,
        retry_reason="rate_limit",
        attempt=2,
        max_attempts=3,
        wait_seconds=10,
    )

    assert (
        retry.message
        == "Notion rate limit reached. Retrying in 10s... (2 items synced so far)"
    )
