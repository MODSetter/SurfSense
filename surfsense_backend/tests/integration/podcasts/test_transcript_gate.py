"""The transcript go/no-go gate: approve to render, or regenerate to redraft.

From ``awaiting_review`` the user either approves (start rendering) or regenerates
(redraft). These pin the resulting state, the Celery task each enqueues, and the
HTTP codes for acting from the wrong state (409) or without a transcript (422).
"""

from __future__ import annotations

import pytest

from app.podcasts.persistence import Podcast, PodcastStatus

pytestmark = pytest.mark.integration

BASE = "/api/v1/podcasts"


async def test_approve_transcript_starts_rendering_and_enqueues_render(
    client, db_search_space, make_podcast, captured_tasks
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.AWAITING_REVIEW
    )

    resp = await client.post(f"{BASE}/{podcast.id}/transcript/approve")

    assert resp.status_code == 200
    assert resp.json()["status"] == "rendering"
    assert captured_tasks.render == [((podcast.id,), {})]
    assert captured_tasks.draft == []


async def test_regenerate_returns_to_drafting_and_enqueues_draft(
    client, db_search_space, make_podcast, captured_tasks
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.AWAITING_REVIEW
    )

    resp = await client.post(f"{BASE}/{podcast.id}/transcript/regenerate")

    assert resp.status_code == 200
    assert resp.json()["status"] == "drafting"
    assert captured_tasks.draft == [((podcast.id, db_search_space.id), {})]
    assert captured_tasks.render == []


async def test_approve_transcript_from_terminal_state_is_rejected(
    client, db_search_space, make_podcast, captured_tasks
):
    # A ready podcast still has its transcript, so the precondition passes and
    # the disallowed terminal->rendering transition is what surfaces (409).
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )

    resp = await client.post(f"{BASE}/{podcast.id}/transcript/approve")

    assert resp.status_code == 409
    assert captured_tasks.render == []


async def test_approve_without_transcript_is_unprocessable(
    client, db_session, db_search_space, captured_tasks
):
    # An anomalous awaiting_review row with no transcript exercises the route's
    # precondition->422 mapping (the service refuses to render without one).
    podcast = Podcast(
        title="No transcript",
        search_space_id=db_search_space.id,
        status=PodcastStatus.AWAITING_REVIEW,
        spec_version=1,
    )
    db_session.add(podcast)
    await db_session.flush()

    resp = await client.post(f"{BASE}/{podcast.id}/transcript/approve")

    assert resp.status_code == 422
    assert captured_tasks.render == []
