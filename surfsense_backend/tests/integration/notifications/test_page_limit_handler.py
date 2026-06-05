"""Behavior guard for the page-limit notification handler."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSpace, User
from app.notifications.service import NotificationService

pytestmark = pytest.mark.integration

handler = NotificationService.page_limit


async def test_page_limit_message_and_action(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """A page-limit notification states usage and carries an upgrade action link."""
    notification = await handler.notify_page_limit_exceeded(
        session=db_session,
        user_id=db_user.id,
        document_name="short.pdf",
        document_type="FILE",
        search_space_id=db_search_space.id,
        pages_used=95,
        pages_limit=100,
        pages_to_add=10,
    )

    assert notification.type == "page_limit_exceeded"
    assert notification.title == "Page limit exceeded: short.pdf"
    assert notification.message == (
        "This document has ~10 page(s) but you've used 95/100 pages. "
        "Upgrade to process more documents."
    )
    assert notification.notification_metadata["status"] == "failed"
    assert notification.notification_metadata["action_label"] == "Upgrade Plan"
    assert notification.notification_metadata["action_url"] == (
        f"/dashboard/{db_search_space.id}/more-pages"
    )


async def test_page_limit_truncates_long_name(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """A long document name is truncated in the notification title."""
    long_name = "a" * 50

    notification = await handler.notify_page_limit_exceeded(
        session=db_session,
        user_id=db_user.id,
        document_name=long_name,
        document_type="FILE",
        search_space_id=db_search_space.id,
        pages_used=95,
        pages_limit=100,
        pages_to_add=10,
    )

    assert notification.title == f"Page limit exceeded: {'a' * 40}..."
