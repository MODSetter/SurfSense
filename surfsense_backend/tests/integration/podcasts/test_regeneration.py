"""Regeneration: the listen-then-redo loop after the brief gate.

The brief is the only approval; drafting flows straight into rendering. A user
who dislikes the finished audio sends the episode back with regenerate. These
pin the READY -> DRAFTING round trip (with the draft task enqueued) and the 409
for regenerating from states that have nothing to redo.
"""

from __future__ import annotations

import pytest

from app.podcasts.persistence import PodcastStatus

pytestmark = pytest.mark.integration

BASE = "/api/v1/podcasts"


async def test_regenerate_from_ready_returns_to_drafting_and_enqueues_draft(
    client, db_search_space, make_podcast, captured_tasks
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )

    resp = await client.post(f"{BASE}/{podcast.id}/transcript/regenerate")

    assert resp.status_code == 200
    assert resp.json()["status"] == "drafting"
    assert captured_tasks.draft == [((podcast.id, db_search_space.id), {})]
    assert captured_tasks.render == []


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
