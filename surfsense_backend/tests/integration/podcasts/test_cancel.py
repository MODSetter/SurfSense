"""Cancelling a podcast: allowed while in flight, refused once an episode exists.

Cancellation is the escape hatch for a podcast that has produced nothing yet.
Once a finished episode exists — including during a regeneration, whose audio
survives until a new render commits — cancel is refused (409): reverting the
regeneration is the way back, and no user action may destroy playable audio.
"""

import pytest

from app.podcasts.persistence import PodcastStatus

pytestmark = pytest.mark.integration

BASE = "/api/v1/podcasts"


async def test_cancel_from_a_live_state_succeeds(client, db_workspace, make_podcast):
    podcast = await make_podcast(
        workspace_id=db_workspace.id, status=PodcastStatus.AWAITING_BRIEF
    )

    resp = await client.post(f"{BASE}/{podcast.id}/cancel")

    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_cancel_from_a_terminal_state_conflicts(
    client, db_workspace, make_podcast
):
    podcast = await make_podcast(
        workspace_id=db_workspace.id, status=PodcastStatus.READY
    )

    resp = await client.post(f"{BASE}/{podcast.id}/cancel")

    assert resp.status_code == 409


async def test_cancel_of_a_regeneration_is_rejected(
    client, db_workspace, make_podcast
):
    # Cancelling here would destroy a playable episode; reverting the
    # regeneration is the way back.
    podcast = await make_podcast(
        workspace_id=db_workspace.id, status=PodcastStatus.READY
    )
    await client.post(f"{BASE}/{podcast.id}/transcript/regenerate")

    resp = await client.post(f"{BASE}/{podcast.id}/cancel")

    assert resp.status_code == 409
    # The regeneration is still revertable afterwards.
    follow_up = await client.post(f"{BASE}/{podcast.id}/regenerate/revert")
    assert follow_up.status_code == 200
    assert follow_up.json()["status"] == "ready"
