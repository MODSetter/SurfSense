"""Behavior guard for the comment-reply notification handler."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSpace, User
from app.notifications.service import NotificationService

pytestmark = pytest.mark.integration

handler = NotificationService.comment_reply


async def _notify(db_session, db_user, db_search_space, *, reply_id=1, preview="hi"):
    """Raise a comment-reply notification for the assertions in the tests below."""
    return await handler.notify_comment_reply(
        session=db_session,
        user_id=db_user.id,
        reply_id=reply_id,
        parent_comment_id=10,
        message_id=20,
        thread_id=30,
        thread_title="Thread",
        author_id="author-1",
        author_name="Bob",
        author_avatar_url=None,
        author_email="bob@surfsense.net",
        content_preview=preview,
        search_space_id=db_search_space.id,
    )


async def test_comment_reply_title_and_message(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """A reply notification names the author and carries the comment preview."""
    notification = await _notify(db_session, db_user, db_search_space, preview="thanks")

    assert notification.type == "comment_reply"
    assert notification.title == "Bob replied in a thread"
    assert notification.message == "thanks"


async def test_comment_reply_truncates_long_preview(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """A long comment preview is truncated in the reply message."""
    notification = await _notify(
        db_session, db_user, db_search_space, preview="y" * 150
    )

    assert notification.message == "y" * 100 + "..."


async def test_comment_reply_is_idempotent(
    db_session: AsyncSession, db_user: User, db_search_space: SearchSpace
):
    """Re-notifying the same reply id reuses the existing notification row."""
    first = await _notify(db_session, db_user, db_search_space, reply_id=5)
    second = await _notify(db_session, db_user, db_search_space, reply_id=5)

    assert second.id == first.id
