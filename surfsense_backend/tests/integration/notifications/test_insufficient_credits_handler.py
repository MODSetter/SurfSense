"""Behavior guard for the insufficient-credits notification handler."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSpace, User
from app.notifications.service import NotificationService

pytestmark = pytest.mark.integration

handler = NotificationService.insufficient_credits


async def test_insufficient_credits_message_and_action(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """An insufficient-credits notification states cost and carries a buy-credits link."""
    notification = await handler.notify_insufficient_credits(
        session=db_session,
        user_id=db_user.id,
        document_name="short.pdf",
        document_type="FILE",
        search_space_id=db_search_space.id,
        balance_micros=250_000,
        required_micros=1_000_000,
    )

    assert notification.type == "insufficient_credits"
    assert notification.title == "Insufficient credits: short.pdf"
    assert notification.message == (
        "This document costs about $1.00 to process but you have "
        "$0.25 of credit left. Add more credits to continue."
    )
    assert notification.notification_metadata["status"] == "failed"
    assert notification.notification_metadata["action_label"] == "Buy credits"
    assert notification.notification_metadata["action_url"] == (
        f"/dashboard/{db_search_space.id}/buy-more"
    )


async def test_insufficient_credits_truncates_long_name(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """A long document name is truncated in the notification title."""
    long_name = "a" * 50

    notification = await handler.notify_insufficient_credits(
        session=db_session,
        user_id=db_user.id,
        document_name=long_name,
        document_type="FILE",
        search_space_id=db_search_space.id,
        balance_micros=250_000,
        required_micros=1_000_000,
    )

    assert notification.title == f"Insufficient credits: {'a' * 40}..."
