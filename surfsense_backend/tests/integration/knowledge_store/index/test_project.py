"""Commit-time projection: rows the UI can read before anything is embedded.

Same real stack as the converger (git engine, Redis lock, Postgres) minus the
indexing pipeline, because not calling it is the point — these tests assert that
a row exists with no chunks behind it, and that the indexer still runs afterwards
and agrees with what the projection wrote.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

import app.knowledge_store.locks as write_lock
from app.config import config as app_config
from app.db import Chunk, Document, Folder, Workspace
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.identities import user_identity
from app.knowledge_store.index.converge import index_changes
from app.knowledge_store.index.project import project_revision
from app.knowledge_store.locks import workspace_index_lock

pytestmark = pytest.mark.integration

# Git recognises a moved file by its content, so a move test needs a body worth
# matching at the new path.
MOVABLE = "# Content\n\na body git can match at its new path\n"


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def store(knowledge_root, db_workspace):
    return KnowledgeStore.for_workspace(db_workspace.id)


async def commit(store, writes=None, removes=()):
    async with store.transaction(message="test", author=user_identity("1")) as tx:
        for path, markdown in (writes or {}).items():
            tx.write(path, markdown.encode())
        for path in removes:
            tx.remove(path)
    return tx.revision


async def titles(session, workspace_id) -> dict[str, Document]:
    result = await session.execute(
        select(Document).where(Document.workspace_id == workspace_id)
    )
    return {document.title: document for document in result.scalars()}


async def chunk_count(session, workspace_id) -> int:
    result = await session.execute(
        select(func.count(Chunk.id))
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.workspace_id == workspace_id)
    )
    return result.scalar_one()


# ── What the UI gets ────────────────────────────────────────────────────────


async def test_a_committed_note_has_its_row_before_it_is_indexed(
    store, db_session, db_workspace
):
    """The whole point: the sidebar can render this without waiting to embed."""
    revision = await commit(store, {"documents/note.xml": "# Note\n\nbody\n"})

    projection = await project_revision(db_session, db_workspace.id, revision)

    assert [document.title for document in projection.created] == ["note"]
    rows = await titles(db_session, db_workspace.id)
    assert set(rows) == {"note"}
    assert await chunk_count(db_session, db_workspace.id) == 0


async def test_the_projection_reports_the_id_the_ui_needs(
    store, db_session, db_workspace
):
    """An event without a real row id would show a document nothing can open."""
    revision = await commit(store, {"documents/note.xml": "# Note\n\nbody\n"})

    projection = await project_revision(db_session, db_workspace.id, revision)

    rows = await titles(db_session, db_workspace.id)
    assert projection.created[0].id == rows["note"].id
    assert projection.created[0].virtual_path == "/documents/note.xml"


async def test_a_second_write_is_an_update_not_a_create(
    store, db_session, db_workspace
):
    await commit(store, {"documents/note.xml": "# First\n"})
    await project_revision(
        db_session, db_workspace.id, (await store.get_current_revision())
    )
    revision = await commit(store, {"documents/note.xml": "# Second\n"})

    projection = await project_revision(db_session, db_workspace.id, revision)

    assert not projection.created
    assert [document.title for document in projection.updated] == ["note"]
    rows = await titles(db_session, db_workspace.id)
    assert rows["note"].source_markdown == "# Second\n"


async def test_a_move_keeps_the_document_id(store, db_session, db_workspace):
    """Citations in earlier answers name this id; a move must not mint a new one."""
    first = await commit(store, {"documents/old.xml": MOVABLE})
    await project_revision(db_session, db_workspace.id, first)
    before = (await titles(db_session, db_workspace.id))["old"].id

    revision = await commit(
        store, writes={"documents/new.xml": MOVABLE}, removes=["documents/old.xml"]
    )
    await project_revision(db_session, db_workspace.id, revision)

    # Title is Postgres-owned, so the move keeps it; the path is what follows.
    result = await db_session.execute(
        select(Document).where(Document.workspace_id == db_workspace.id)
    )
    rows = {d.path: d for d in result.scalars()}
    assert set(rows) == {"/documents/new.xml"}
    assert rows["/documents/new.xml"].id == before


async def test_a_removed_file_loses_its_row(store, db_session, db_workspace):
    first = await commit(store, {"documents/note.xml": "# Note\n"})
    await project_revision(db_session, db_workspace.id, first)

    revision = await commit(store, removes=["documents/note.xml"])
    projection = await project_revision(db_session, db_workspace.id, revision)

    assert [document.title for document in projection.deleted] == ["note"]
    assert await titles(db_session, db_workspace.id) == {}


async def test_an_empty_keep_folder_gets_its_row_at_commit_time(
    store, db_session, db_workspace
):
    """The sidebar shows an agent's empty folder without waiting for the indexer;
    the ``.keep`` is a blank the doc loop skips, so the row comes from the tree."""
    revision = await commit(store, {"documents/Smoking rules/.keep": ""})

    await project_revision(db_session, db_workspace.id, revision)

    names = (
        (
            await db_session.execute(
                select(Folder.name).where(Folder.workspace_id == db_workspace.id)
            )
        )
        .scalars()
        .all()
    )
    assert "Smoking rules" in names
    assert await titles(db_session, db_workspace.id) == {}


# ── Staying out of the indexer's way ────────────────────────────────────────


async def test_the_projection_does_not_claim_the_revision_is_indexed(
    store, db_session, db_workspace
):
    """Stamping here would tell the drift sweep to skip a workspace with no chunks."""
    revision = await commit(store, {"documents/note.xml": "# Note\n"})

    await project_revision(db_session, db_workspace.id, revision)

    workspace = await db_session.get(Workspace, db_workspace.id)
    assert workspace.last_indexed_revision is None


async def test_indexing_after_a_projection_adopts_the_same_row(
    store, db_session, db_workspace, patched_embed_texts
):
    """Two writers, one row: the indexer must not insert a duplicate."""
    revision = await commit(store, {"documents/note.xml": "# Note\n\nbody\n"})
    await project_revision(db_session, db_workspace.id, revision)
    projected_id = (await titles(db_session, db_workspace.id))["note"].id

    await index_changes(db_session, db_workspace.id)

    rows = await titles(db_session, db_workspace.id)
    assert set(rows) == {"note"}
    assert rows["note"].id == projected_id
    assert await chunk_count(db_session, db_workspace.id) > 0


async def test_a_held_index_lock_makes_the_projection_stand_aside(
    store, db_session, db_workspace, monkeypatch
):
    """A rebuild is already writing these rows; the turn must not wait for it."""
    monkeypatch.setattr(write_lock, "INDEX_LOCK_WAIT_SECONDS", 0.1)
    revision = await commit(store, {"documents/note.xml": "# Note\n"})

    async with workspace_index_lock(db_workspace.id):
        projection = await project_revision(db_session, db_workspace.id, revision)

    assert not projection
    assert await titles(db_session, db_workspace.id) == {}


async def test_a_test_only_workspace_id_is_dropped(store, db_session, db_workspace):
    """Same contract as enqueue_index: no numeric id, no row to project onto."""
    revision = await commit(store, {"documents/note.xml": "# Note\n"})

    assert not await project_revision(db_session, "it-abc123", revision)
