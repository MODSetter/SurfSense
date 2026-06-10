"""Behavior guard for the document-processing notification handler."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSpace, User
from app.notifications.service import NotificationService

pytestmark = pytest.mark.integration

handler = NotificationService.document_processing


async def _started(db_session, db_user, db_search_space, *, name="report.pdf"):
    """Open a document-processing notification to update in the tests below."""
    return await handler.notify_processing_started(
        session=db_session,
        user_id=db_user.id,
        document_type="FILE",
        document_name=name,
        search_space_id=db_search_space.id,
    )


async def test_processing_started_queues(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """Starting processing queues a notification in the 'queued' stage."""
    notification = await _started(db_session, db_user, db_search_space)

    assert notification.type == "document_processing"
    assert notification.title == "Processing: report.pdf"
    assert notification.message == "Waiting in queue"
    assert notification.notification_metadata["processing_stage"] == "queued"


async def test_processing_progress_maps_stage(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """A progress update maps the stage to its user-facing message."""
    notification = await _started(db_session, db_user, db_search_space)

    updated = await handler.notify_processing_progress(
        session=db_session, notification=notification, stage="parsing"
    )

    assert updated.message == "Reading your file"
    assert updated.notification_metadata["processing_stage"] == "parsing"


async def test_processing_completed_success(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """Successful processing reports ready/searchable and a completed status."""
    notification = await _started(db_session, db_user, db_search_space)

    done = await handler.notify_processing_completed(
        session=db_session, notification=notification, document_id=99
    )

    assert done.title == "Ready: report.pdf"
    assert done.message == "Now searchable!"
    assert done.notification_metadata["status"] == "completed"


async def test_processing_completed_failure(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """Failed processing reports a failed status with the error in the message."""
    notification = await _started(db_session, db_user, db_search_space)

    done = await handler.notify_processing_completed(
        session=db_session, notification=notification, error_message="bad file"
    )

    assert done.title == "Failed: report.pdf"
    assert done.message == "Processing failed: bad file"
    assert done.notification_metadata["status"] == "failed"
