"""The audio-rendering task against a real database.

From RENDERING, the task synthesises and merges the approved transcript, stores
the bytes, and marks the podcast READY with the storage location recorded. The
DB, service, renderer orchestration, and storage wrapper run for real; the true
externals are faked — the TTS provider, the FFmpeg merge, and the object store.
"""

from __future__ import annotations

import pytest

from app.podcasts.persistence import PodcastStatus
from app.podcasts.tasks import render

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
