"""Behavior guard for the notifications inbox HTTP API.

Rows are seeded through the transactional db_session and read back through the
real endpoints (auth + DB bound to the same transaction), pinning list filters,
counts, mark-read semantics, and response mapping.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User
from app.notifications.persistence import Notification

pytestmark = pytest.mark.integration

BASE = "/api/v1/notifications"


async def _seed(
    db_session: AsyncSession,
    user: User,
    *,
    type: str = "document_processing",
    title: str = "Title",
    message: str = "Message",
    read: bool = False,
    search_space_id: int | None = None,
    metadata: dict | None = None,
    created_at: datetime | None = None,
) -> Notification:
    """Insert a notification row directly for the API tests to read back."""
    notification = Notification(
        user_id=user.id,
        search_space_id=search_space_id,
        type=type,
        title=title,
        message=message,
        read=read,
        notification_metadata=metadata or {},
    )
    if created_at is not None:
        notification.created_at = created_at
    db_session.add(notification)
    await db_session.flush()
    return notification


async def test_list_returns_user_notifications_mapped(client, db_session, db_user):
    """GET / returns the caller's notifications mapped to the response shape."""
    seeded = await _seed(
        db_session, db_user, type="document_processing", title="Doc done"
    )

    resp = await client.get(BASE)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == seeded.id
    assert item["user_id"] == str(db_user.id)
    assert item["type"] == "document_processing"
    assert item["title"] == "Doc done"
    assert item["read"] is False
    assert item["created_at"]  # ISO string present


async def test_list_orders_newest_first(client, db_session, db_user):
    """The list is ordered by creation time, newest first."""
    now = datetime.now(UTC)
    await _seed(db_session, db_user, title="older", created_at=now - timedelta(hours=2))
    await _seed(db_session, db_user, title="newer", created_at=now)

    resp = await client.get(BASE)

    titles = [item["title"] for item in resp.json()["items"]]
    assert titles == ["newer", "older"]


async def test_list_filters_by_category(client, db_session, db_user):
    """The category filter narrows results to that category's notification types."""
    await _seed(db_session, db_user, type="connector_indexing", title="status item")
    await _seed(db_session, db_user, type="comment_reply", title="comment item")

    resp = await client.get(BASE, params={"category": "comments"})

    titles = [item["title"] for item in resp.json()["items"]]
    assert titles == ["comment item"]


async def test_list_filters_unread_only(client, db_session, db_user):
    """The unread filter returns only notifications that haven't been read."""
    await _seed(db_session, db_user, title="unread one", read=False)
    await _seed(db_session, db_user, title="read one", read=True)

    resp = await client.get(BASE, params={"filter": "unread"})

    titles = [item["title"] for item in resp.json()["items"]]
    assert titles == ["unread one"]


async def test_list_filters_by_connector_source_type(client, db_session, db_user):
    """A 'connector:<type>' source filter selects only that connector's notifications."""
    await _seed(
        db_session,
        db_user,
        type="connector_indexing",
        title="github",
        metadata={"connector_type": "GITHUB_CONNECTOR"},
    )
    await _seed(
        db_session,
        db_user,
        type="connector_indexing",
        title="notion",
        metadata={"connector_type": "NOTION_CONNECTOR"},
    )

    resp = await client.get(BASE, params={"source_type": "connector:GITHUB_CONNECTOR"})

    titles = [item["title"] for item in resp.json()["items"]]
    assert titles == ["github"]


async def test_list_rejects_invalid_before_date(client, db_session, db_user):
    """A malformed before_date is rejected with a 400."""
    await _seed(db_session, db_user)

    resp = await client.get(BASE, params={"before_date": "not-a-date"})

    assert resp.status_code == 400


async def test_list_paginates_with_has_more(client, db_session, db_user):
    """Pagination caps the page and reports has_more plus the next offset."""
    now = datetime.now(UTC)
    for i in range(3):
        await _seed(
            db_session, db_user, title=f"n{i}", created_at=now - timedelta(minutes=i)
        )

    resp = await client.get(BASE, params={"limit": 2, "offset": 0})

    body = resp.json()
    assert len(body["items"]) == 2
    assert body["has_more"] is True
    assert body["next_offset"] == 2


async def test_unread_count_splits_total_and_recent(client, db_session, db_user):
    """The unread count reports total unread and a recent-window subset."""
    now = datetime.now(UTC)
    await _seed(db_session, db_user, read=False, created_at=now)
    await _seed(db_session, db_user, read=False, created_at=now - timedelta(days=30))
    await _seed(db_session, db_user, read=True, created_at=now)

    resp = await client.get(f"{BASE}/unread-count")

    body = resp.json()
    assert body["total_unread"] == 2
    assert body["recent_unread"] == 1


async def test_unread_counts_batch_by_category(client, db_session, db_user):
    """The batch endpoint breaks unread counts down per category."""
    await _seed(db_session, db_user, type="comment_reply", read=False)
    await _seed(db_session, db_user, type="connector_indexing", read=False)

    resp = await client.get(f"{BASE}/unread-counts-batch")

    body = resp.json()
    assert body["comments"]["total_unread"] == 1
    assert body["status"]["total_unread"] == 1


async def test_mark_read_then_idempotent(client, db_session, db_user):
    """Marking read succeeds, and a repeat call is a no-op reporting already-read."""
    notification = await _seed(db_session, db_user, read=False)

    first = await client.patch(f"{BASE}/{notification.id}/read")
    assert first.status_code == 200
    assert first.json()["success"] is True

    second = await client.patch(f"{BASE}/{notification.id}/read")
    assert second.status_code == 200
    assert second.json()["message"] == "Notification already marked as read"


async def test_mark_read_foreign_notification_404(client, db_session, db_user):
    """Marking another user's notification read returns 404, not a cross-user write."""
    other = User(
        email="other@surfsense.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(other)
    await db_session.flush()
    foreign = await _seed(db_session, other, read=False)

    resp = await client.patch(f"{BASE}/{foreign.id}/read")

    assert resp.status_code == 404


async def test_mark_all_read_returns_count(client, db_session, db_user):
    """Mark-all-read flips only the unread rows and returns how many changed."""
    await _seed(db_session, db_user, read=False)
    await _seed(db_session, db_user, read=False)
    await _seed(db_session, db_user, read=True)

    resp = await client.patch(f"{BASE}/read-all")

    body = resp.json()
    assert body["success"] is True
    assert body["updated_count"] == 2
