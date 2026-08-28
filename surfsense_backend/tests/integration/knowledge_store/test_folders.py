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
    # The reported symptom: git can't track empty dirs, so the removal must also
    # prune the folder off disk instead of leaving a hollow shell behind.
    assert not (knowledge_root / str(db_workspace.id) / "documents" / "Trash").exists()


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


async def test_a_document_folder_change_reparents_its_git_file(
    knowledge_root, db_session, db_workspace, db_user
):
    """The document-move route's contract: a folder_id change tells git, so a
    rebuild finds the file at the new folder rather than resurrecting the old.
    """
    from app.db import DocumentStatus, DocumentType
    from app.knowledge_store.service import (
        record_moved_documents,
        record_saved_document,
    )
    from app.services.folder_service import ensure_folder_hierarchy

    store = _store(db_workspace, db_session, db_user)
    document = Document(
        title="note",
        document_type=DocumentType.NOTE,
        document_metadata={},
        content="# note",
        content_hash="hash-note",
        unique_identifier_hash="unique-note",
        source_markdown="# note",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        status=DocumentStatus.ready(),
    )
    db_session.add(document)
    await db_session.flush()
    await record_saved_document(
        db_session,
        workspace_id=db_workspace.id,
        doc_id=document.id,
        title="note",
        folder_id=None,
        markdown="# note\n\na body to index\n",
        author_user_id=str(db_user.id),
    )
    before = document.path  # authored at the root

    target = await ensure_folder_hierarchy(
        db_session,
        workspace_id=db_workspace.id,
        created_by_id=str(db_user.id),
        folder_parts=["B"],
    )
    document.folder_id = target
    await db_session.flush()
    await record_moved_documents(db_session, [document], author_user_id=str(db_user.id))
    await db_session.commit()

    moved = document.path
    filename = before.rsplit("/", 1)[-1]
    assert moved == f"/documents/B/{filename}"  # reparented, name unchanged
    paths = await _paths(store, await store.head())
    assert f"documents/B/{filename}" in paths
    assert before.lstrip("/") not in paths


async def test_move_folder_keeps_the_folder_id(
    knowledge_root, db_session, db_workspace, db_user
):
    """A rename moves the row in place, so its id — and its children — survive."""
    store = _store(db_workspace, db_session, db_user)
    await store.create_folder("/documents/Old/Child")
    original = (
        await db_session.execute(
            select(Folder).where(
                Folder.workspace_id == db_workspace.id, Folder.name == "Old"
            )
        )
    ).scalar_one()
    child_before = (
        await db_session.execute(
            select(Folder).where(
                Folder.workspace_id == db_workspace.id, Folder.name == "Child"
            )
        )
    ).scalar_one()

    await store.move_folder("/documents/Old", "/documents/New")

    renamed = (
        await db_session.execute(
            select(Folder).where(
                Folder.workspace_id == db_workspace.id, Folder.name == "New"
            )
        )
    ).scalar_one()
    assert renamed.id == original.id
    assert "Old" not in await _folder_names(db_session, db_workspace.id)
    # The child rode along on parent_id; its own id is untouched too.
    assert renamed.id == child_before.parent_id


async def test_remove_folder_markers_keeps_documents(
    knowledge_root, db_session, db_workspace, db_user
):
    """Delete drops a folder's empty markers but leaves its files to the purge."""
    store = _store(db_workspace, db_session, db_user)
    await store.create_folder("/documents/Docs/Empty")
    body = "# Note\n\na body long enough for the indexer to embed and chunk\n"
    await store.write("documents/Docs/note.md", body)

    outcome = await store.remove_folder_markers("/documents/Docs")

    paths = await _paths(store, outcome.revision)
    assert "documents/Docs/note.md" in paths
    assert not any(p.rsplit("/", 1)[-1] == KEEP_FILE for p in paths)
    names = await _folder_names(db_session, db_workspace.id)
    assert "Empty" not in names and "Docs" in names


async def test_record_created_folder_gives_a_row_git_presence(
    knowledge_root, db_session, db_workspace, db_user
):
    """The create route's contract: a committed row is materialized in git."""
    from app.knowledge_store.service import record_created_folder
    from app.services.folder_service import ensure_folder_hierarchy

    store = _store(db_workspace, db_session, db_user)
    await ensure_folder_hierarchy(
        db_session,
        workspace_id=db_workspace.id,
        created_by_id=str(db_user.id),
        folder_parts=["Fresh"],
    )
    folder = (
        await db_session.execute(
            select(Folder).where(
                Folder.workspace_id == db_workspace.id, Folder.name == "Fresh"
            )
        )
    ).scalar_one()

    await record_created_folder(db_session, folder, author_user_id=str(db_user.id))

    assert f"documents/Fresh/{KEEP_FILE}" in await _paths(store, await store.head())


async def test_route_rename_flow_keeps_the_folder_id(
    knowledge_root, db_session, db_workspace, db_user
):
    """The route renames the row, then records the move; git follows, id kept.

    Order matters: the row is already at its new name when the move records, so
    the in-place reparent is a no-op and git still moves the subtree.
    """
    from app.knowledge_store.service import folder_virtual_path, record_moved_folder

    store = _store(db_workspace, db_session, db_user)
    await store.create_folder("/documents/Old")
    folder = (
        await db_session.execute(
            select(Folder).where(
                Folder.workspace_id == db_workspace.id, Folder.name == "Old"
            )
        )
    ).scalar_one()

    source = await folder_virtual_path(db_session, folder)
    folder.name = "New"
    await db_session.commit()
    await db_session.refresh(folder)
    destination = await folder_virtual_path(db_session, folder)
    await record_moved_folder(
        db_session,
        db_workspace.id,
        source=source,
        destination=destination,
        author_user_id=str(db_user.id),
    )

    assert source == "/documents/Old"
    assert destination == "/documents/New"
    paths = await _paths(store, await store.head())
    assert f"documents/New/{KEEP_FILE}" in paths
    assert not any(p.startswith("documents/Old/") for p in paths)
    renamed = (
        await db_session.execute(
            select(Folder).where(
                Folder.workspace_id == db_workspace.id, Folder.name == "New"
            )
        )
    ).scalar_one()
    assert renamed.id == folder.id


def test_keep_is_rejected_as_a_document_path():
    with pytest.raises(StorePathError):
        StorePath.from_virtual(f"/documents/x/{KEEP_FILE}")
