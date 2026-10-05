"""A scope as large as the sources tree can send: every file ticked but thousands."""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, insert

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.source_roots.managed_root import ensure_managed_root
from modules.workspaces.models import Workspace
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

UNTICKED = 5_000


def _library(engine: Engine, notes: int) -> tuple[int, list[int]]:
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Archive")
        session.add(workspace)
        session.flush()
        library = ensure_managed_root(session, workspace.id)
        ids = list(
            session.scalars(
                insert(Document).returning(Document.id),
                [
                    {
                        "workspace_id": workspace.id,
                        "title": f"note {n}",
                        "document_type": DocumentType.NOTE,
                        "status": DocumentStatus.READY,
                        "content": "text",
                        "folder_id": library.id,
                    }
                    for n in range(notes)
                ],
            )
        )
        session.commit()
        return workspace.id, sorted(ids)


async def test_thousands_of_unticked_files_are_stored_and_resolved(
    client: AsyncClient, engine: Engine
) -> None:
    """A cap of 1,000 made every send from such a tree a 422."""
    workspace_id, ids = _library(engine, UNTICKED + 1)
    scope = {"all": True, "excluded_document_ids": ids[1:]}
    thread = await client.post(f"/workspaces/{workspace_id}/chat/threads", json={})

    drafted = await client.post(
        f"/workspaces/{workspace_id}/source-scope/resolve", json=scope
    )
    stored = await client.put(
        f"/chat/threads/{thread.json()['id']}/source-scope", json=scope
    )

    assert drafted.status_code == 200
    assert drafted.json()["counts"]["ready"] == 1
    assert stored.status_code == 200
    assert stored.json()["counts"]["ready"] == 1
    assert len(stored.json()["source_scope"]["excluded_document_ids"]) == UNTICKED


async def test_a_scope_past_the_cap_is_still_refused(
    client: AsyncClient, engine: Engine
) -> None:
    """The cap still bounds a request body."""
    workspace_id, _ = _library(engine, 1)

    refused = await client.post(
        f"/workspaces/{workspace_id}/source-scope/resolve",
        json={"document_ids": list(range(1, 50_002))},
    )

    assert refused.status_code == 422
