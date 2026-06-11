"""Streaming a podcast's rendered audio over HTTP.

A ready podcast streams its bytes from the storage backend; a podcast with no
stored audio returns 404. Storage is an in-memory backend (the object store is a
system boundary).
"""

from __future__ import annotations

import pytest

from app.podcasts.persistence import PodcastStatus

pytestmark = pytest.mark.integration

BASE = "/api/v1/podcasts"


async def test_stream_serves_stored_audio(
    client, db_search_space, make_podcast, fake_storage
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )
    fake_storage.objects["podcasts/audio.mp3"] = b"the-audio"

    resp = await client.get(f"{BASE}/{podcast.id}/stream")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"the-audio"


async def test_stream_404_when_no_audio(client, db_search_space, make_podcast):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.AWAITING_REVIEW
    )

    resp = await client.get(f"{BASE}/{podcast.id}/stream")

    assert resp.status_code == 404
