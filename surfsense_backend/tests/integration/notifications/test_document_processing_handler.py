"""Behavior guard for the document-processing notification handler."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Workspace, User
from app.notifications.service import NotificationService

pytestmark = pytest.mark.integration

handler = NotificationService.document_processing


async def _started(db_session, db_user, db_workspace, *, name="report.pdf"):
    """Open a document-processing notification to update in the tests below."""
    return await handler.notify_processing_started(
        session=db_session,
        user_id=db_user.id,
        document_type="FILE",
        document_name=name,
        workspace_id=db_workspace.id,
    )


async def test_processing_started_queues(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    """Starting processing queues a notification in the 'queued' stage."""
    notification = await _started(db_session, db_user, db_workspace)

    assert notification.type == "document_processing"
    assert notification.title == "Processing: report.pdf"
    assert notification.message == "Waiting in queue"
    assert notification.notification_metadata["processing_stage"] == "queued"


async def test_processing_progress_maps_stage(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    """A progress update maps the stage to its user-facing message."""
    notification = await _started(db_session, db_user, db_workspace)

    updated = await handler.notify_processing_progress(
        session=db_session, notification=notification, stage="parsing"
    )

    assert updated.message == "Reading your file"
    assert updated.notification_metadata["processing_stage"] == "parsing"


async def test_processing_completed_success(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    """Successful processing reports ready/searchable and a completed status."""
    notification = await _started(db_session, db_user, db_workspace)

    done = await handler.notify_processing_completed(
        session=db_session, notification=notification, document_id=99
    )

    assert done.title == "Ready: report.pdf"
    assert done.message == "Now searchable!"
    assert done.notification_metadata["status"] == "completed"


async def test_processing_completed_failure(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    """Failed processing reports a failed status with the error in the message."""
    notification = await _started(db_session, db_user, db_workspace)

    done = await handler.notify_processing_completed(
        session=db_session, notification=notification, error_message="bad file"
    )

    assert done.title == "Failed: report.pdf"
    assert done.message == "Processing failed: bad file"
    assert done.notification_metadata["status"] == "failed"


async def test_processing_started_truncates_long_filename(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    """A long filename is truncated in the title but kept in metadata."""
    long_name = "a" * 250

    notification = await handler.notify_processing_started(
        session=db_session,
        user_id=db_user.id,
        document_type="FILE",
        document_name=long_name,
        workspace_id=db_workspace.id,
    )

    assert len(notification.title) <= 200
    assert notification.title.startswith("Processing: ")
    assert notification.title.endswith("...")
    assert notification.notification_metadata["document_name"] == long_name
