"""Cancelling a podcast: allowed while in flight, refused once terminal.

Cancellation is a user escape hatch from any non-terminal state; a podcast that
has already finished (READY) has no exit, so the disallowed transition surfaces
as 409.
"""

import pytest

from app.podcasts.persistence import PodcastStatus

pytestmark = pytest.mark.integration

BASE = "/api/v1/podcasts"


async def test_cancel_from_a_live_state_succeeds(
    client, db_search_space, make_podcast
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.AWAITING_BRIEF
    )

    resp = await client.post(f"{BASE}/{podcast.id}/cancel")

    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_cancel_from_a_terminal_state_conflicts(
    client, db_search_space, make_podcast
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )

    resp = await client.post(f"{BASE}/{podcast.id}/cancel")

    assert resp.status_code == 409
