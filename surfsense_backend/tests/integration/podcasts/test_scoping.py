"""Podcasts are scoped to workspace membership.

A user can only create or read podcasts in spaces they belong to, and an
unscoped listing returns only the caller's own podcasts — never another
member's.
"""

import pytest

pytestmark = pytest.mark.integration

BASE = "/api/v1/podcasts"


async def test_reading_a_podcast_in_a_nonmember_space_is_forbidden(
    client, db_workspace, make_podcast, act_as, db_other_user
):
    podcast = await make_podcast(workspace_id=db_workspace.id)
    act_as(db_other_user)

    resp = await client.get(f"{BASE}/{podcast.id}")

    assert resp.status_code == 403


async def test_creating_in_a_nonmember_space_is_forbidden(
    client, db_workspace, act_as, db_other_user
):
    act_as(db_other_user)

    resp = await client.post(
        BASE,
        json={
            "title": "X",
            "workspace_id": db_workspace.id,
            "source_content": "content",
        },
    )

    assert resp.status_code == 403


async def test_listing_returns_only_the_callers_podcasts(
    client, db_workspace, make_podcast, foreign_podcast
):
    mine = await make_podcast(workspace_id=db_workspace.id, title="Mine")

    resp = await client.get(BASE)

    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert mine.id in ids
    assert foreign_podcast.id not in ids
