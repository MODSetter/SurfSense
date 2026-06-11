"""Public (unauthenticated) podcast streaming from a chat snapshot.

A shared chat snapshot carries each podcast's stored-audio key; the public route
streams those bytes from the object store via ``share_token`` with no auth. A
podcast that isn't in the snapshot is a 404.
"""

import pytest

from app.db import NewChatThread, PublicChatSnapshot, User

pytestmark = pytest.mark.integration


async def _snapshot(db_session, *, search_space_id, user: User, token: str, podcasts):
    thread = NewChatThread(
        title="Shared", search_space_id=search_space_id, created_by_id=user.id
    )
    db_session.add(thread)
    await db_session.flush()
    snapshot = PublicChatSnapshot(
        thread_id=thread.id,
        share_token=token,
        content_hash=f"hash-{token}",
        message_ids=[],
        snapshot_data={"podcasts": podcasts},
    )
    db_session.add(snapshot)
    await db_session.flush()


async def test_public_stream_serves_audio_via_storage_key(
    client, db_session, db_search_space, db_user, fake_storage
):
    await _snapshot(
        db_session,
        search_space_id=db_search_space.id,
        user=db_user,
        token="tok-audio",
        podcasts=[{"original_id": 555, "storage_key": "podcasts/x.mp3"}],
    )
    fake_storage.objects["podcasts/x.mp3"] = b"public-audio"

    resp = await client.get("/api/v1/public/tok-audio/podcasts/555/stream")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"public-audio"


async def test_public_stream_404_when_podcast_absent_from_snapshot(
    client, db_session, db_search_space, db_user
):
    await _snapshot(
        db_session,
        search_space_id=db_search_space.id,
        user=db_user,
        token="tok-empty",
        podcasts=[],
    )

    resp = await client.get("/api/v1/public/tok-empty/podcasts/999/stream")

    assert resp.status_code == 404
