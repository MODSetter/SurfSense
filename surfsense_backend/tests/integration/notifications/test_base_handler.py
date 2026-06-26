"""Behavior guard for the shared find/upsert/update logic (BaseNotificationHandler).

Uses the connector-indexing handler instance to drive the base methods against
real Postgres, pinning upsert dedup, workspace scoping, and status stamping.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Workspace, User
from app.notifications.persistence import Notification
from app.notifications.service import NotificationService

pytestmark = pytest.mark.integration

handler = NotificationService.connector_indexing


async def test_find_or_create_creates_with_progress_metadata(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """Creating a notification seeds operation id, in-progress status, and start time."""
    notification = await handler.find_or_create_notification(
        session=db_session,
        user_id=db_user.id,
        operation_id="op-create",
        title="Title",
        message="Message",
        workspace_id=db_workspace.id,
    )

    assert notification.notification_metadata["operation_id"] == "op-create"
    assert notification.notification_metadata["status"] == "in_progress"
    assert "started_at" in notification.notification_metadata


async def test_find_or_create_upserts_same_operation(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """Reusing an operation id updates the same row instead of creating a duplicate."""
    first = await handler.find_or_create_notification(
        session=db_session,
        user_id=db_user.id,
        operation_id="op-upsert",
        title="First",
        message="First message",
        workspace_id=db_workspace.id,
    )

    second = await handler.find_or_create_notification(
        session=db_session,
        user_id=db_user.id,
        operation_id="op-upsert",
        title="Second",
        message="Second message",
        workspace_id=db_workspace.id,
    )

    assert second.id == first.id
    assert second.title == "Second"
    assert second.message == "Second message"

    count = await db_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == db_user.id,
            Notification.notification_metadata["operation_id"].astext == "op-upsert",
        )
    )
    assert count == 1


async def test_find_by_operation_is_scoped_to_workspace(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """Operation-id lookup is scoped per workspace, so other spaces don't match."""
    await handler.find_or_create_notification(
        session=db_session,
        user_id=db_user.id,
        operation_id="op-scoped",
        title="Title",
        message="Message",
        workspace_id=db_workspace.id,
    )

    other_space = Workspace(name="Other Space", user_id=db_user.id)
    db_session.add(other_space)
    await db_session.flush()

    found_other = await handler.find_notification_by_operation(
        session=db_session,
        user_id=db_user.id,
        operation_id="op-scoped",
        workspace_id=other_space.id,
    )
    assert found_other is None

    found_same = await handler.find_notification_by_operation(
        session=db_session,
        user_id=db_user.id,
        operation_id="op-scoped",
        workspace_id=db_workspace.id,
    )
    assert found_same is not None


async def test_update_notification_completed_stamps_completed_at(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """Completing a notification stamps completed_at and merges metadata updates."""
    notification = await handler.find_or_create_notification(
        session=db_session,
        user_id=db_user.id,
        operation_id="op-complete",
        title="Title",
        message="Message",
        workspace_id=db_workspace.id,
    )

    updated = await handler.update_notification(
        session=db_session,
        notification=notification,
        status="completed",
        metadata_updates={"indexed_count": 7},
    )

    assert updated.notification_metadata["status"] == "completed"
    assert "completed_at" in updated.notification_metadata
    assert updated.notification_metadata["indexed_count"] == 7


async def test_update_notification_failed_stamps_completed_at(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """Failing a notification also stamps completed_at for the terminal state."""
    notification = await handler.find_or_create_notification(
        session=db_session,
        user_id=db_user.id,
        operation_id="op-fail",
        title="Title",
        message="Message",
        workspace_id=db_workspace.id,
    )

    updated = await handler.update_notification(
        session=db_session,
        notification=notification,
        status="failed",
    )

    assert updated.notification_metadata["status"] == "failed"
    assert "completed_at" in updated.notification_metadata
