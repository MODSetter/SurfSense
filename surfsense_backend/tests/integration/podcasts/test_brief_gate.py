"""The brief review gate: edit the spec, then approve to start drafting.

Covers what the user can do while ``awaiting_brief`` — edit the brief under
optimistic concurrency and approve it — and the HTTP status codes the service's
guards map to when an edit races or comes too late.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

BASE = "/api/v1/podcasts"


async def _create(client, workspace_id: int) -> dict:
    resp = await client.post(
        BASE,
        json={
            "title": "Episode",
            "workspace_id": workspace_id,
            "source_content": "Source content.",
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_approve_brief_starts_drafting_and_enqueues_draft(
    client, db_workspace, captured_tasks
):
    podcast = await _create(client, db_workspace.id)

    resp = await client.post(f"{BASE}/{podcast['id']}/brief/approve")

    assert resp.status_code == 200
    assert resp.json()["status"] == "drafting"
    assert captured_tasks.draft == [((podcast["id"], db_workspace.id), {})]
    assert captured_tasks.render == []


async def test_update_spec_bumps_version_and_persists(client, db_workspace):
    podcast = await _create(client, db_workspace.id)
    spec = podcast["spec"]
    spec["focus"] = "A sharper angle"

    resp = await client.patch(
        f"{BASE}/{podcast['id']}/spec",
        json={"spec": spec, "expected_version": podcast["spec_version"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["spec_version"] == podcast["spec_version"] + 1
    assert body["spec"]["focus"] == "A sharper angle"
    assert body["status"] == "awaiting_brief"


async def test_update_spec_with_stale_version_conflicts(client, db_workspace):
    podcast = await _create(client, db_workspace.id)

    resp = await client.patch(
        f"{BASE}/{podcast['id']}/spec",
        json={"spec": podcast["spec"], "expected_version": 999},
    )

    assert resp.status_code == 409


async def test_update_spec_after_approval_is_rejected(client, db_workspace):
    podcast = await _create(client, db_workspace.id)
    await client.post(f"{BASE}/{podcast['id']}/brief/approve")

    resp = await client.patch(
        f"{BASE}/{podcast['id']}/spec",
        json={"spec": podcast["spec"], "expected_version": podcast["spec_version"]},
    )

    assert resp.status_code == 409
