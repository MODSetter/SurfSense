"""The audio-rendering task against a real database.

From RENDERING, the task synthesises and merges the approved transcript, stores
the bytes, and marks the podcast READY with the storage location recorded. The
DB, service, renderer orchestration, and storage wrapper run for real; the true
externals are faked — the TTS provider, the FFmpeg merge, and the object store.
"""

from __future__ import annotations

import pytest

from app.podcasts.persistence import PodcastStatus
from app.podcasts.service import PodcastService
from app.podcasts.tasks import render

from .conftest import build_transcript

pytestmark = pytest.mark.integration


async def test_render_marks_ready_and_stores_audio(
    db_search_space, make_podcast, bind_task_session, fake_tts, fake_merge, fake_storage
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.RENDERING
    )

    result = await render._render_audio(podcast.id)

    assert result["status"] == "ready"
    assert podcast.status == PodcastStatus.READY
    assert podcast.storage_backend == "memory"
    assert podcast.storage_key
    assert fake_storage.objects[podcast.storage_key] == b"merged-audio"


async def test_rerender_replaces_audio_and_purges_the_old_object(
    db_session,
    db_search_space,
    make_podcast,
    bind_task_session,
    fake_tts,
    fake_merge,
    fake_storage,
):
    # A regenerated episode keeps exactly one stored object: the new render
    # must not leak the superseded audio in the object store.
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )
    old_key = podcast.storage_key
    fake_storage.objects[old_key] = b"old-audio"

    service = PodcastService(db_session)
    await service.regenerate(podcast)
    await service.attach_transcript(podcast, build_transcript())

    result = await render._render_audio(podcast.id)

    assert result["status"] == "ready"
    assert podcast.status == PodcastStatus.READY
    assert podcast.storage_key != old_key
    assert fake_storage.objects[podcast.storage_key] == b"merged-audio"
    assert old_key in fake_storage.deleted
