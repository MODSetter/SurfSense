"""Before onboarding fixes the embedder, nothing that would be embedded is taken.

Onboarding gates the UI only; the API is reached directly too, by scripts and
plugins, and a document accepted now would have no model to be embedded with.
"""

import pytest
from httpx import AsyncClient

from shared.queue import ingest_queue

pytestmark = pytest.mark.integration

NOT_CHOSEN = {
    "code": "embedding_not_chosen",
    "message": "no embedding model has been chosen yet",
}


@pytest.fixture
async def workspace_id(unlocked_client: AsyncClient) -> int:
    """Workspaces need no embedder, so one exists before onboarding finishes."""
    created = await unlocked_client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])


async def test_a_note_is_refused(
    unlocked_client: AsyncClient, workspace_id: int
) -> None:
    """Refused before a row is written or a job is queued."""
    reply = await unlocked_client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "Kickoff", "content": "agreed to ship"},
    )

    assert reply.status_code == 409
    assert reply.json()["detail"] == NOT_CHOSEN
    listed = await unlocked_client.get(f"/workspaces/{workspace_id}/documents")
    assert listed.json() == []
    assert ingest_queue.pending_count() == 0


async def test_an_upload_is_refused(
    unlocked_client: AsyncClient, workspace_id: int
) -> None:
    """The bytes are not kept either: nothing would ever embed them."""
    reply = await unlocked_client.post(
        f"/workspaces/{workspace_id}/documents/upload",
        files={"files": ("report.pdf", b"%PDF-1.7 fake", "application/pdf")},
    )

    assert reply.status_code == 409
    assert reply.json()["detail"] == NOT_CHOSEN
    assert ingest_queue.pending_count() == 0
