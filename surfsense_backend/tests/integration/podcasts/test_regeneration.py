"""Regeneration: the listen-then-redo loop after the brief gate.

A user who dislikes the finished audio sends the episode back to the brief
gate: the saved brief reopens for tweaks (voices, length, focus) and drafting
only restarts on a fresh approval. The whole redo can also be reverted at any
point before the new render commits, falling back to the still-stored episode.
These pin the READY -> AWAITING_BRIEF -> DRAFTING round trip, the revert
fallback, and the 409s for acting from states that have nothing to redo or
revert.
"""

from __future__ import annotations

import pytest

from app.podcasts.persistence import Podcast, PodcastStatus
from app.podcasts.service import PodcastService

from .conftest import build_transcript

pytestmark = pytest.mark.integration

BASE = "/api/v1/podcasts"


async def test_regenerate_from_ready_reopens_the_brief_gate(
    client, db_search_space, make_podcast, captured_tasks
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )

    resp = await client.post(f"{BASE}/{podcast.id}/transcript/regenerate")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "awaiting_brief"
    # The prior brief is kept as the starting point for the new take.
    assert body["spec"] is not None
    # Nothing drafts until the user approves the reopened brief.
    assert captured_tasks.draft == []
    assert captured_tasks.render == []


async def test_approving_the_reopened_brief_starts_a_fresh_draft(
    client, db_search_space, make_podcast, captured_tasks
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )
    await client.post(f"{BASE}/{podcast.id}/transcript/regenerate")

    resp = await client.post(f"{BASE}/{podcast.id}/brief/approve")

    assert resp.status_code == 200
    assert resp.json()["status"] == "drafting"
    assert captured_tasks.draft == [((podcast.id, db_search_space.id), {})]


async def test_regenerate_from_brief_gate_is_rejected(
    client, db_search_space, make_podcast, captured_tasks
):
    # Nothing has been drafted yet, so there is nothing to regenerate.
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.AWAITING_BRIEF
    )

    resp = await client.post(f"{BASE}/{podcast.id}/transcript/regenerate")

    assert resp.status_code == 409
    assert captured_tasks.draft == []


async def test_regenerate_from_cancelled_is_rejected(
    client, db_search_space, make_podcast, captured_tasks
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.AWAITING_BRIEF
    )
    await client.post(f"{BASE}/{podcast.id}/cancel")

    resp = await client.post(f"{BASE}/{podcast.id}/transcript/regenerate")

    assert resp.status_code == 409
    assert captured_tasks.draft == []


async def test_reverting_a_regeneration_restores_the_ready_episode(
    client, db_search_space, make_podcast, captured_tasks
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )
    await client.post(f"{BASE}/{podcast.id}/transcript/regenerate")

    resp = await client.post(f"{BASE}/{podcast.id}/regenerate/revert")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    # The episode the user could already play is untouched.
    assert body["has_audio"] is True
    assert captured_tasks.draft == []
    assert captured_tasks.render == []


async def test_reverting_mid_draft_keeps_the_episode(
    client, db_search_space, make_podcast
):
    # Changing one's mind is allowed even after the reopened brief was
    # approved: the episode survives until a new render replaces it.
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )
    await client.post(f"{BASE}/{podcast.id}/transcript/regenerate")
    await client.post(f"{BASE}/{podcast.id}/brief/approve")

    resp = await client.post(f"{BASE}/{podcast.id}/regenerate/revert")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


async def test_reverting_mid_render_keeps_the_episode(
    client, db_session, db_search_space, make_podcast
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )
    service = PodcastService(db_session)
    await service.regenerate(podcast)
    await service.begin_drafting(podcast)
    await service.attach_transcript(podcast, build_transcript())

    resp = await client.post(f"{BASE}/{podcast.id}/regenerate/revert")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


async def test_reverted_episode_can_be_regenerated_again(
    client, db_search_space, make_podcast
):
    # Reverting must not strand the episode: the user can change their mind
    # again immediately.
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )
    await client.post(f"{BASE}/{podcast.id}/transcript/regenerate")
    await client.post(f"{BASE}/{podcast.id}/regenerate/revert")

    resp = await client.post(f"{BASE}/{podcast.id}/transcript/regenerate")

    assert resp.status_code == 200
    assert resp.json()["status"] == "awaiting_brief"


async def test_revert_on_a_fresh_brief_gate_is_rejected(
    client, db_search_space, make_podcast
):
    # A first-time brief has no regeneration to revert.
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.AWAITING_BRIEF
    )

    resp = await client.post(f"{BASE}/{podcast.id}/regenerate/revert")

    assert resp.status_code == 409
    assert resp.json()["detail"]


async def test_revert_when_nothing_was_regenerated_is_rejected(
    client, db_search_space, make_podcast
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )

    resp = await client.post(f"{BASE}/{podcast.id}/regenerate/revert")

    assert resp.status_code == 409


async def test_regenerate_without_a_brief_is_rejected(
    client, db_session, db_search_space, captured_tasks
):
    # Legacy episodes finished before briefs existed; reopening a gate with
    # nothing to review would strand them there.
    podcast = Podcast(
        title="Legacy Episode",
        search_space_id=db_search_space.id,
        status=PodcastStatus.READY,
        spec_version=1,
        file_location="/var/old/podcast.mp3",
    )
    db_session.add(podcast)
    await db_session.flush()

    resp = await client.post(f"{BASE}/{podcast.id}/transcript/regenerate")

    assert resp.status_code == 422
    assert captured_tasks.draft == []
