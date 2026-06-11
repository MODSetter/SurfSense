"""Regeneration: the listen-then-redo loop after the brief gate.

A user who dislikes the finished audio sends the episode back to the brief
gate: the saved brief reopens for tweaks (voices, length, focus) and drafting
only restarts on a fresh approval. These pin the READY -> AWAITING_BRIEF ->
DRAFTING round trip and the 409 for regenerating from states that have nothing
to redo.
"""

from __future__ import annotations

import pytest

from app.podcasts.persistence import PodcastStatus

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
