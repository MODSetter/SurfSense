"""Behavior guard for the @mention notification handler."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSpace, User
from app.notifications.service import NotificationService

pytestmark = pytest.mark.integration

handler = NotificationService.mention


async def _notify(db_session, db_user, db_search_space, *, mention_id=1, preview="hi"):
    """Raise an @mention notification for the assertions in the tests below."""
    return await handler.notify_new_mention(
        session=db_session,
        mentioned_user_id=db_user.id,
        mention_id=mention_id,
        comment_id=10,
        message_id=20,
        thread_id=30,
        thread_title="Thread",
        author_id="author-1",
        author_name="Alice",
        author_avatar_url=None,
        author_email="alice@surfsense.net",
        content_preview=preview,
        search_space_id=db_search_space.id,
    )


async def test_new_mention_title_and_message(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """A mention notification names the author and carries the comment preview."""
    notification = await _notify(db_session, db_user, db_search_space, preview="hello")

    assert notification.type == "new_mention"
    assert notification.title == "Alice mentioned you"
    assert notification.message == "hello"


async def test_new_mention_truncates_long_preview(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """A long comment preview is truncated in the mention message."""
    notification = await _notify(
        db_session, db_user, db_search_space, preview="x" * 150
    )

    assert notification.message == "x" * 100 + "..."


async def test_new_mention_is_idempotent(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """Re-notifying the same mention id reuses the existing notification row."""
    first = await _notify(db_session, db_user, db_search_space, mention_id=7)
    second = await _notify(db_session, db_user, db_search_space, mention_id=7)

    assert second.id == first.id
