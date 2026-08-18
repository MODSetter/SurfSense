"""Podcasts are scoped to workspace membership.

A user can only create or read podcasts in spaces they belong to.
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
