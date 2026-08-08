"""The load-bearing symmetry: one path, one row, on both sides of the boundary.

Author a path into git, project it to a row, and the path the UI reads is the
same string git stores — and resolving it back finds the one row that authored
it. When these fork, a document has two identities and the filesystem dies quietly.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import config as app_config
from app.db import Document
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.index.converge import index_changes
from app.knowledge_store.paths import StorePath, virtual_path_to_doc

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


async def test_the_projected_path_round_trips_to_the_git_store_path(
    knowledge_root, db_session, db_workspace, db_user
):
    store = (
        KnowledgeStore.for_workspace(db_workspace.id)
        .with_session(db_session)
        .as_user(str(db_user.id))
    )
    await store.write(
        "documents/notes/plan.md", "# Plan\n\na body the indexer can chunk\n"
    )

    await index_changes(db_session, db_workspace.id)

    document = (
        await db_session.execute(
            select(Document).where(Document.workspace_id == db_workspace.id)
        )
    ).scalar_one()
    # The row the UI reads carries the git path verbatim, and it round-trips.
    assert document.path == "/documents/notes/plan.md"
    assert StorePath.from_virtual(document.path).store_path == "documents/notes/plan.md"

    resolved = await virtual_path_to_doc(
        db_session, workspace_id=db_workspace.id, virtual_path=document.path
    )
    assert resolved is not None and resolved.id == document.id
