"""Folder law: folders start in the store, empty ones via a ``.keep`` marker.

Real git engine + real DB. A folder verb is one revision that projects to
``folders`` rows; ``.keep`` never becomes a document.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.config import config as app_config
from app.db import Document, Folder
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.index.converge import index_changes, index_tree
from app.knowledge_store.paths import KEEP_FILE, StorePath, StorePathError

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))

    async def _enabled(_workspace_id):
        return True

    monkeypatch.setattr(
        "app.knowledge_store.service.knowledge_store_enabled_for", _enabled
    )
    return tmp_path


def _store(db_workspace, db_session, db_user) -> KnowledgeStore:
    return (
        KnowledgeStore.for_workspace(db_workspace.id)
        .with_session(db_session)
        .as_user(str(db_user.id))
    )


async def _paths(store, revision) -> set[str]:
    return {t.path for t in await store.list_paths(revision)}


async def _folder_names(session, workspace_id) -> set[str]:
    rows = await session.execute(
        select(Folder.name).where(Folder.workspace_id == workspace_id)
    )
    return set(rows.scalars())


async def _doc_count(session, workspace_id) -> int:
    return await session.scalar(
        select(func.count(Document.id)).where(Document.workspace_id == workspace_id)
    )


async def test_create_folder_materializes_an_empty_folder(
    knowledge_root, db_session, db_workspace, db_user
):
    store = _store(db_workspace, db_session, db_user)

    outcome = await store.create_folder("/documents/Research/Ideas")

    assert outcome.revision is not None
    assert f"documents/Research/Ideas/{KEEP_FILE}" in await _paths(
        store, outcome.revision
    )
    assert await _folder_names(db_session, db_workspace.id) == {"Research", "Ideas"}
    assert await _doc_count(db_session, db_workspace.id) == 0


async def test_an_empty_folder_survives_a_rebuild(
    knowledge_root, db_session, db_workspace, db_user
):
    store = _store(db_workspace, db_session, db_user)
    await store.create_folder("/documents/Empty")

    await index_tree(db_session, db_workspace.id)

    assert "Empty" in await _folder_names(db_session, db_workspace.id)
    assert await _doc_count(db_session, db_workspace.id) == 0


async def test_remove_folder_prunes_rows_and_clears_the_subtree(
    knowledge_root, db_session, db_workspace, db_user
):
    store = _store(db_workspace, db_session, db_user)
    await store.create_folder("/documents/Trash/Deep")

    outcome = await store.remove_folder("/documents/Trash")

    assert outcome.revision is not None
    assert not any(
        p.startswith("documents/Trash/") for p in await _paths(store, outcome.revision)
    )
    names = await _folder_names(db_session, db_workspace.id)
    assert "Trash" not in names and "Deep" not in names


async def test_move_folder_keeps_the_document_id(
    knowledge_root, db_session, db_workspace, db_user
):
    store = _store(db_workspace, db_session, db_user)
    body = "# Note\n\na body long enough for the indexer to embed and chunk\n"
    await store.write("documents/A/note.md", body)
    await index_changes(db_session, db_workspace.id)
    original = (
        await db_session.execute(
            select(Document).where(Document.workspace_id == db_workspace.id)
        )
    ).scalar_one()

    # A move converges through the incremental path, where the diff since the last
    # revision carries the rename that keeps the id (a full rebuild has no rename).
    await store.move_folder("/documents/A", "/documents/B")
    await index_changes(db_session, db_workspace.id)

    moved = (
        await db_session.execute(
            select(Document).where(Document.workspace_id == db_workspace.id)
        )
    ).scalar_one()
    assert moved.id == original.id
    assert moved.path == "/documents/B/note.md"


def test_keep_is_rejected_as_a_document_path():
    with pytest.raises(StorePathError):
        StorePath.from_virtual(f"/documents/x/{KEEP_FILE}")
