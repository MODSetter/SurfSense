"""The audio-rendering task against a real database.

From RENDERING the task synthesises and merges the approved transcript, records
the delivered Artifact (which owns the audio), stamps ``artifact_id``, and marks
the podcast READY. The DB, service, renderer orchestration, and artifact service
run for real; the true externals are faked — the TTS provider, the FFmpeg merge,
and the object store.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.artifacts.persistence import ArtifactFile, ArtifactFileRole
from app.podcasts.persistence import PodcastStatus
from app.podcasts.service import PodcastService
from app.podcasts.tasks import render

from .conftest import build_transcript

pytestmark = pytest.mark.integration


async def _primary_key(db_session, artifact_id: int) -> str:
    row = await db_session.scalar(
        select(ArtifactFile).where(
            ArtifactFile.artifact_id == artifact_id,
            ArtifactFile.role == ArtifactFileRole.PRIMARY,
        )
    )
    assert row is not None
    return row.storage_key


async def test_render_marks_ready_and_records_the_artifact(
    db_session, db_workspace, make_podcast, bind_task_session, fake_tts, fake_merge, fake_storage
):
    podcast = await make_podcast(
        workspace_id=db_workspace.id, status=PodcastStatus.RENDERING
    )

    result = await render._render_audio(podcast.id)

    assert result["status"] == "ready"
    assert podcast.status == PodcastStatus.READY
    assert podcast.artifact_id is not None
    key = await _primary_key(db_session, podcast.artifact_id)
    assert fake_storage.objects[key] == b"merged-audio"


async def test_rerender_reuses_the_artifact_and_purges_the_old_object(
    db_session,
    db_workspace,
    make_podcast,
    bind_task_session,
    fake_tts,
    fake_merge,
    fake_storage,
):
    podcast = await make_podcast(
        workspace_id=db_workspace.id, status=PodcastStatus.READY
    )
    original_artifact_id = podcast.artifact_id
    old_key = await _primary_key(db_session, original_artifact_id)

    service = PodcastService(db_session)
    await service.regenerate(podcast)
    await service.begin_drafting(podcast)
    await service.attach_transcript(podcast, build_transcript())

    result = await render._render_audio(podcast.id)

    assert result["status"] == "ready"
    assert podcast.status == PodcastStatus.READY
    # The Artifact is revised in place, not replaced.
    assert podcast.artifact_id == original_artifact_id
    new_key = await _primary_key(db_session, podcast.artifact_id)
    assert new_key != old_key
    assert fake_storage.objects[new_key] == b"merged-audio"
    assert old_key in fake_storage.deleted


async def test_render_losing_to_a_user_revert_keeps_the_episode(
    db_session,
    db_workspace,
    make_podcast,
    bind_task_session,
    fake_tts,
    fake_merge,
    fake_storage,
):
    # The user reverts the regeneration while the render is in flight: the
    # stale render must not finalize a new take.
    podcast = await make_podcast(
        workspace_id=db_workspace.id, status=PodcastStatus.READY
    )
    original_artifact_id = podcast.artifact_id

    service = PodcastService(db_session)
    await service.regenerate(podcast)
    await service.begin_drafting(podcast)
    await service.attach_transcript(podcast, build_transcript())
    await service.revert_regeneration(podcast)

    result = await render._render_audio(podcast.id)

    assert result["status"] == "superseded"
    assert podcast.status == PodcastStatus.READY
    assert podcast.artifact_id == original_artifact_id
