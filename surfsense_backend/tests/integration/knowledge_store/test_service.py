"""Document saves become store revisions (real git engine + real Redis lock)."""

from __future__ import annotations

import uuid

import pytest

from app.config import config as app_config
from app.db import Document, DocumentStatus, DocumentType
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.paths import PATH_MARKER
from app.knowledge_store.service import (
    drop_workspace_store,
    record_deleted_documents,
    record_markdown_files,
    record_moved_documents,
    record_prepared_documents,
    record_saved_document,
)
from app.services.folder_service import ensure_folder_hierarchy

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


async def test_one_save_records_one_revision(knowledge_root, workspace_id):
    revision = await record_markdown_files(
        workspace_id=workspace_id,
        files={"documents/notes/meeting.md": "# Meeting"},
        message="docs: save meeting.md",
        author_user_id="1",
    )

    store = KnowledgeStore.for_workspace(workspace_id)
    assert revision is not None
    assert (
        await store.read_as_of(revision, "documents/notes/meeting.md") == b"# Meeting"
    )
    rev = (await store.list_revisions())[0]
    assert "1" in rev.author
    assert "meeting.md" in rev.message


async def test_a_sync_batch_records_one_revision(knowledge_root, workspace_id):
    revision = await record_markdown_files(
        workspace_id=workspace_id,
        files={
            "documents/notion/roadmap.md": "# Roadmap",
            "documents/notion/okrs.md": "# OKRs",
        },
        message="sync: index 2 document(s)",
        author_user_id="1",
    )

    store = KnowledgeStore.for_workspace(workspace_id)
    revisions = await store.list_revisions()
    assert [r.id for r in revisions] == [revision]
    assert await store.read_as_of(revision, "documents/notion/okrs.md") == b"# OKRs"


async def test_unchanged_content_records_nothing(knowledge_root, workspace_id):
    files = {"documents/notion/roadmap.md": "# Roadmap"}
    first = await record_markdown_files(
        workspace_id=workspace_id, files=files, message="sync", author_user_id="1"
    )
    second = await record_markdown_files(
        workspace_id=workspace_id, files=files, message="sync", author_user_id="1"
    )

    assert first is not None
    assert second is None
    assert len(await KnowledgeStore.for_workspace(workspace_id).list_revisions()) == 1


async def test_empty_batch_records_nothing(knowledge_root, workspace_id):
    revision = await record_markdown_files(
        workspace_id=workspace_id, files={}, message="sync", author_user_id="1"
    )

    assert revision is None
    assert not (knowledge_root / str(workspace_id)).exists()


async def test_a_retitled_document_leaves_no_file_at_its_old_path(
    knowledge_root, workspace_id
):
    """One document is one file. Without the removal a retitle forks it into two."""
    await record_markdown_files(
        workspace_id=workspace_id,
        files={"documents/Old title.xml": "# Body"},
        message="docs: save Old title.xml",
        author_user_id="1",
    )

    revision = await record_markdown_files(
        workspace_id=workspace_id,
        files={"documents/New title.xml": "# Body"},
        message="docs: save New title.xml",
        author_user_id="1",
        removes=["documents/Old title.xml"],
    )

    store = KnowledgeStore.for_workspace(workspace_id)
    paths = {entry.path for entry in await store.list_paths(revision)}
    assert paths == {"documents/New title.xml"}


async def test_disabled_store_records_nothing(monkeypatch, tmp_path, workspace_id):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", False)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))

    revision = await record_markdown_files(
        workspace_id=workspace_id,
        files={"documents/notes/meeting.md": "# Meeting"},
        message="docs: save meeting.md",
        author_user_id="1",
    )

    assert revision is None
    assert not (tmp_path / str(workspace_id)).exists()


# --- record_saved_document: the editor's path resolution and retitle handling ---
#
# The tests above hand `removes` in ready-made, so they only prove the batch
# primitive honours it. These drive the caller that has to *derive* the removal
# from the row's path marker — the step a retitle depends on.


async def _make_document(session, workspace, user, title: str) -> Document:
    document = Document(
        title=title,
        document_type=DocumentType.NOTE,
        document_metadata={},
        content=f"# {title}",
        content_hash=f"hash-{uuid.uuid4().hex}",
        unique_identifier_hash=f"unique-{uuid.uuid4().hex}",
        source_markdown=f"# {title}",
        workspace_id=workspace.id,
        created_by_id=user.id,
        status=DocumentStatus.ready(),
    )
    session.add(document)
    await session.commit()
    return document


async def _save(
    session,
    workspace,
    user,
    document,
    *,
    title,
    markdown="# Body",
    title_is_explicit=False,
):
    return await record_saved_document(
        session,
        workspace_id=workspace.id,
        doc_id=document.id,
        title=title,
        folder_id=None,
        markdown=markdown,
        author_user_id=str(user.id),
        title_is_explicit=title_is_explicit,
    )


async def _store_paths(workspace, revision: str) -> set[str]:
    store = KnowledgeStore.for_workspace(workspace.id)
    return {entry.path for entry in await store.list_paths(revision)}


async def test_a_save_records_the_document_and_remembers_its_path(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")

    revision = await _save(
        db_session, db_workspace, db_user, document, title="Meeting notes"
    )

    assert revision is not None
    paths = await _store_paths(db_workspace, revision)
    assert len(paths) == 1
    assert "Meeting notes" in next(iter(paths))
    # Remembered so the *next* save knows where the document used to live.
    assert "Meeting notes" in document.path


async def test_a_new_document_is_authored_as_markdown(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """The live write path stamps ``.md`` now, not the legacy ``.xml``."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")

    revision = await _save(
        db_session, db_workspace, db_user, document, title="Meeting notes"
    )

    assert await _store_paths(db_workspace, revision) == {"documents/Meeting notes.md"}
    assert document.path == "/documents/Meeting notes.md"


async def test_a_same_titled_document_gets_a_numbered_name(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """Two files cannot share one path; the second breaks the tie with ``(2)``."""
    workspace_flip(True)
    first = await _make_document(db_session, db_workspace, db_user, "Report")
    await _save(db_session, db_workspace, db_user, first, title="Report")
    second = await _make_document(db_session, db_workspace, db_user, "Report")

    await _save(db_session, db_workspace, db_user, second, title="Report")

    assert first.path == "/documents/Report.md"
    assert second.path == "/documents/Report (2).md"


async def test_a_resave_of_an_unmarked_row_reattaches_instead_of_forking(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """The editor twin of ``test_a_reingest_of_an_unmarked_row_reattaches...``.

    A row can lose both its marker and its path column — the crash window between
    the git commit and the mark. Its file is still in git. A re-save must
    re-attach to that file by the row's identity, not author ``Meeting notes
    (2).md`` and strand the first. Ingest already heals this; save authored a
    fresh path instead, so the two live writers forked the same row two ways.
    One placement decision, one outcome."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")
    first = await _save(db_session, db_workspace, db_user, document, title="Meeting notes")
    recorded = next(iter(await _store_paths(db_workspace, first)))

    # The crash window: git kept the file, the row lost the link back to it.
    document.document_metadata = {}
    document.path = None
    await db_session.commit()

    second = await _save(
        db_session,
        db_workspace,
        db_user,
        document,
        title="Meeting notes",
        markdown="# Meeting notes\n\nEdited.",
    )

    assert await _store_paths(db_workspace, second) == {recorded}


async def test_a_retitle_leaves_only_the_new_path(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """The removal has to be derived from the recorded path, not supplied by the
    caller."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Old title")
    await _save(db_session, db_workspace, db_user, document, title="Old title")

    document.title = "New title"
    revision = await _save(
        db_session,
        db_workspace,
        db_user,
        document,
        title="New title",
        title_is_explicit=True,
    )

    paths = await _store_paths(db_workspace, revision)
    assert len(paths) == 1
    assert "New title" in next(iter(paths))
    assert "New title" in document.path


async def test_a_retitle_records_the_move_as_one_revision(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """Two revisions, not three: the drop rides along with the write."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Old title")
    await _save(db_session, db_workspace, db_user, document, title="Old title")

    document.title = "New title"
    await _save(
        db_session,
        db_workspace,
        db_user,
        document,
        title="New title",
        title_is_explicit=True,
    )

    store = KnowledgeStore.for_workspace(db_workspace.id)
    assert len(await store.list_revisions()) == 2


async def _agent_authored(session, workspace, user, path: str, markdown: str):
    """A file under a name no title would derive, with the row that points at it."""
    await record_markdown_files(
        workspace_id=workspace.id,
        files={path.lstrip("/"): markdown},
        message="agent: write",
        author_user_id=str(user.id),
    )
    document = await _make_document(session, workspace, user, path.rsplit("/", 1)[-1])
    document.path = path
    document.document_metadata = {PATH_MARKER: path}
    await session.commit()
    return document


async def test_an_inferred_retitle_keeps_the_name_the_agent_chose(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """A note's title is re-read from its first heading on every save, so an
    ordinary save arrives here looking like a retitle. Placing by that title
    would rename the agent's file — and invalidate the path it is holding."""
    workspace_flip(True)
    document = await _agent_authored(
        db_session, db_workspace, db_user, "/documents/summary.md", "# Key Points"
    )

    revision = await _save(
        db_session,
        db_workspace,
        db_user,
        document,
        title="Key Points",
        markdown="# Key Points\n\nEdited.",
    )

    assert await _store_paths(db_workspace, revision) == {"documents/summary.md"}
    assert document.path == "/documents/summary.md"


async def test_an_explicit_rename_still_moves_the_agent_s_file(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """The gate narrows which titles place a file; it does not stop a rename."""
    workspace_flip(True)
    document = await _agent_authored(
        db_session, db_workspace, db_user, "/documents/summary.md", "# Key Points"
    )

    revision = await _save(
        db_session,
        db_workspace,
        db_user,
        document,
        title="Key Points",
        markdown="# Key Points\n\nEdited.",
        title_is_explicit=True,
    )

    paths = await _store_paths(db_workspace, revision)
    assert paths == {"documents/Key Points.md"}
    assert document.path == "/documents/Key Points.md"


async def test_no_marker_is_left_when_nothing_was_recorded(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """A marker without a file makes the row look indexer-owned, so a later
    whole-tree converge would prune it."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")
    await _save(db_session, db_workspace, db_user, document, title="Meeting notes")

    document.document_metadata = {}
    await db_session.commit()
    revision = await _save(
        db_session, db_workspace, db_user, document, title="Meeting notes"
    )

    assert revision is None
    assert PATH_MARKER not in document.document_metadata


async def test_a_marker_outside_the_documents_namespace_is_not_dropped(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """Resolving it raises; swallowing that is what keeps the save recordable."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")
    document.document_metadata = {PATH_MARKER: "/elsewhere/foreign.xml"}
    await db_session.commit()

    revision = await _save(
        db_session, db_workspace, db_user, document, title="Meeting notes"
    )

    assert revision is not None
    assert len(await _store_paths(db_workspace, revision)) == 1


async def test_a_save_in_an_unflipped_workspace_records_nothing(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    workspace_flip(False)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")

    revision = await _save(
        db_session, db_workspace, db_user, document, title="Meeting notes"
    )

    assert revision is None
    assert not (knowledge_root / str(db_workspace.id)).exists()


async def test_a_recording_failure_does_not_fail_the_save(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip, monkeypatch
):
    """The Postgres save already committed; the store is the coexisting copy."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")

    async def boom(self, **kwargs):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(KnowledgeStore, "_commit_files", boom)

    revision = await _save(
        db_session, db_workspace, db_user, document, title="Meeting notes"
    )

    assert revision is None
    assert PATH_MARKER not in document.document_metadata


# --- record_prepared_documents: the connector sync batch ---


async def test_a_sync_batch_records_every_document_with_markdown(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    workspace_flip(True)
    first = await _make_document(db_session, db_workspace, db_user, "Roadmap")
    second = await _make_document(db_session, db_workspace, db_user, "OKRs")

    revision = await record_prepared_documents(db_session, [first, second])

    assert revision is not None
    paths = await _store_paths(db_workspace, revision)
    assert len(paths) == 2
    assert any("Roadmap" in path for path in paths)


async def test_a_document_without_markdown_is_left_out_of_the_batch(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """An extraction that produced nothing must not land as an empty file."""
    workspace_flip(True)
    kept = await _make_document(db_session, db_workspace, db_user, "Roadmap")
    empty = await _make_document(db_session, db_workspace, db_user, "Unextracted")
    empty.source_markdown = None
    await db_session.commit()

    revision = await record_prepared_documents(db_session, [kept, empty])

    paths = await _store_paths(db_workspace, revision)
    assert len(paths) == 1
    assert "Roadmap" in next(iter(paths))


async def test_an_empty_sync_batch_records_nothing(
    knowledge_root, db_session, workspace_flip
):
    workspace_flip(True)

    assert await record_prepared_documents(db_session, []) is None


async def test_a_sync_batch_in_an_unflipped_workspace_records_nothing(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    workspace_flip(False)
    document = await _make_document(db_session, db_workspace, db_user, "Roadmap")

    assert await record_prepared_documents(db_session, [document]) is None
    assert not (knowledge_root / str(db_workspace.id)).exists()


async def test_a_sync_batch_failure_does_not_reach_the_caller(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip, monkeypatch
):
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Roadmap")

    async def boom(self, **kwargs):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(KnowledgeStore, "_commit_files", boom)

    assert await record_prepared_documents(db_session, [document]) is None


async def test_a_resync_that_dropped_the_marker_overwrites_in_place(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """The duplication bug this whole change exists for. A connector re-sync
    rewrites metadata with fresh fields that carry no marker; the durable ``path``
    column has to pin the file so the batch overwrites in place instead of
    authoring a second path and forking the document."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Roadmap")

    first = await record_prepared_documents(db_session, [document])
    recorded = next(iter(await _store_paths(db_workspace, first)))

    # The re-sync: marker gone from metadata, path column survives, body changed.
    document.path = f"/{recorded}"
    document.document_metadata = {"md5_checksum": "changed"}
    document.source_markdown = "# Roadmap v2"
    await db_session.commit()

    second = await record_prepared_documents(db_session, [document])

    assert await _store_paths(db_workspace, second) == {recorded}
    store = KnowledgeStore.for_workspace(db_workspace.id)
    assert await store.read_as_of(second, recorded) == b"# Roadmap v2"


async def test_a_resync_that_kept_the_marker_overwrites_in_place(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """The common case: the marker survived the re-sync, so it pins the file and
    the batch is a one-path overwrite, never a fork."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Roadmap")

    first = await record_prepared_documents(db_session, [document])
    recorded = next(iter(await _store_paths(db_workspace, first)))

    document.document_metadata = {PATH_MARKER: f"/{recorded}", "md5_checksum": "x"}
    document.source_markdown = "# Roadmap v2"
    await db_session.commit()

    second = await record_prepared_documents(db_session, [document])

    assert await _store_paths(db_workspace, second) == {recorded}


async def test_a_resync_before_converge_does_not_fork(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """The prod drift engine. A connector re-sync can arrive before projection
    catches up (the doc is still pending/failed, so converge never marked it).
    Ingest has to pin the row itself — write its path back — or the re-sync
    re-authors ``Roadmap (2).md`` against the git tree and strands the first file
    as an orphan. No manual path fix-up here: that is the whole point."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Roadmap")

    first = await record_prepared_documents(db_session, [document])
    recorded = next(iter(await _store_paths(db_workspace, first)))

    # Pinned the moment ingest lands, without waiting for converge.
    assert document.path == f"/{recorded}"

    document.source_markdown = "# Roadmap v2"
    await db_session.commit()
    second = await record_prepared_documents(db_session, [document])

    assert await _store_paths(db_workspace, second) == {recorded}
    store = KnowledgeStore.for_workspace(db_workspace.id)
    assert await store.read_as_of(second, recorded) == b"# Roadmap v2"


async def test_a_reingest_of_an_unmarked_row_reattaches_instead_of_forking(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """A row can lose both its marker and its path column — the crash window
    between the git commit and the mark, and the legacy unmarked-orphan rows in
    production. Its file is still in git. A re-ingest must re-attach to that file
    by the row's identity, not author ``Roadmap (2).md`` and strand the first."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Roadmap")

    first = await record_prepared_documents(db_session, [document])
    recorded = next(iter(await _store_paths(db_workspace, first)))

    document.document_metadata = {}
    document.path = None
    document.source_markdown = "# Roadmap v2"
    await db_session.commit()

    second = await record_prepared_documents(db_session, [document])

    assert await _store_paths(db_workspace, second) == {recorded}


# --- record_deleted_documents: the file has to go with the row ---
#
# Without this verb the row goes and the file stays, so the next whole-tree
# converge reads the file back as a document the user deleted.


async def test_a_delete_removes_the_document_s_file(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")
    await _save(db_session, db_workspace, db_user, document, title="Meeting notes")

    revision = await record_deleted_documents(db_session, [document])

    assert revision is not None
    assert await _store_paths(db_workspace, revision) == set()


async def test_a_delete_follows_the_recorded_path_rather_than_the_title(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """An agent names its own files, so deriving the path from the title deletes
    nothing and leaves the real file behind."""
    workspace_flip(True)
    document = await _agent_authored(
        db_session, db_workspace, db_user, "/documents/summary.md", "# Key Points"
    )

    revision = await record_deleted_documents(db_session, [document])

    assert await _store_paths(db_workspace, revision) == set()


async def test_a_delete_leaves_the_documents_it_was_not_given(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    workspace_flip(True)
    doomed = await _make_document(db_session, db_workspace, db_user, "Doomed")
    kept = await _make_document(db_session, db_workspace, db_user, "Kept")
    await _save(db_session, db_workspace, db_user, doomed, title="Doomed")
    await _save(db_session, db_workspace, db_user, kept, title="Kept")

    revision = await record_deleted_documents(db_session, [doomed])

    paths = await _store_paths(db_workspace, revision)
    assert len(paths) == 1
    assert "Kept" in next(iter(paths))


async def test_a_delete_in_an_unflipped_workspace_records_nothing(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    workspace_flip(False)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")

    assert await record_deleted_documents(db_session, [document]) is None
    assert not (knowledge_root / str(db_workspace.id)).exists()


async def test_a_delete_failure_does_not_reach_the_caller(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip, monkeypatch
):
    """The row still has to go: a store that cannot be reached must not block a
    delete the user asked for. The drift check is what catches the leftover."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")

    async def boom(self, **kwargs):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(KnowledgeStore, "_commit_files", boom)

    assert await record_deleted_documents(db_session, [document]) is None


# --- record_moved_documents: one verb for every path change ---


async def test_a_move_relocates_the_file_and_remembers_where(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Old name")
    await _save(db_session, db_workspace, db_user, document, title="Old name")

    document.title = "New name"
    revision = await record_moved_documents(db_session, [document])

    assert revision is not None
    paths = await _store_paths(db_workspace, revision)
    assert len(paths) == 1
    assert "New name" in next(iter(paths))
    assert "New name" in document.path


async def test_a_move_carries_the_content_the_caller_never_read(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """A folder rename moves documents whose markdown nobody loaded, so the
    content has to come from the store rather than from the caller."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Old name")
    await _save(
        db_session,
        db_workspace,
        db_user,
        document,
        title="Old name",
        markdown="# Body that only git has",
    )

    document.title = "New name"
    revision = await record_moved_documents(db_session, [document])

    store = KnowledgeStore.for_workspace(db_workspace.id)
    destination = next(iter(await _store_paths(db_workspace, revision)))
    assert await store.read_as_of(revision, destination) == b"# Body that only git has"


async def test_a_move_reads_back_as_a_rename(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """The indexer keeps a document's id by detecting the rename in the diff. A
    revision that reads as a delete plus an add churns the id, and saved
    citations and version rows hang off it."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Old name")
    await _save(db_session, db_workspace, db_user, document, title="Old name")

    document.title = "New name"
    revision = await record_moved_documents(db_session, [document])

    store = KnowledgeStore.for_workspace(db_workspace.id)
    changes = await store.list_changes(revision)
    assert [change.kind for change in changes] == ["renamed"]


async def test_a_move_into_a_folder_follows_the_folder(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")
    await _save(db_session, db_workspace, db_user, document, title="Meeting notes")

    document.folder_id = await ensure_folder_hierarchy(
        db_session,
        workspace_id=db_workspace.id,
        created_by_id=str(db_user.id),
        folder_parts=["Archive"],
    )
    revision = await record_moved_documents(db_session, [document])

    paths = await _store_paths(db_workspace, revision)
    assert len(paths) == 1
    assert next(iter(paths)).startswith("documents/Archive/")


async def test_a_document_that_did_not_move_records_nothing(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")
    await _save(db_session, db_workspace, db_user, document, title="Meeting notes")

    assert await record_moved_documents(db_session, [document]) is None


async def test_a_document_with_no_file_yet_has_nothing_to_move(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """No marker means no recorded file. The next save writes it where the row
    now says, so inventing a move here would only fail to find a source."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")

    assert await record_moved_documents(db_session, [document]) is None


async def test_a_move_in_an_unflipped_workspace_records_nothing(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    workspace_flip(False)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")

    assert await record_moved_documents(db_session, [document]) is None
    assert not (knowledge_root / str(db_workspace.id)).exists()


async def test_dropping_a_workspace_takes_its_store_with_it(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Meeting notes")
    await _save(db_session, db_workspace, db_user, document, title="Meeting notes")
    assert (knowledge_root / str(db_workspace.id)).exists()

    await drop_workspace_store(db_workspace.id)

    assert not (knowledge_root / str(db_workspace.id)).exists()


async def test_dropping_a_workspace_that_never_had_a_store_is_quiet(
    knowledge_root, db_workspace
):
    """A workspace deleted before it was ever flipped has nothing on disk."""
    await drop_workspace_store(db_workspace.id)


async def test_a_move_failure_leaves_the_recorded_path_alone(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip, monkeypatch
):
    """A path pointing where the file is not would make the next delete miss."""
    workspace_flip(True)
    document = await _make_document(db_session, db_workspace, db_user, "Old name")
    await _save(db_session, db_workspace, db_user, document, title="Old name")

    async def boom(self, **kwargs):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(KnowledgeStore, "_commit_files", boom)
    document.title = "New name"

    assert await record_moved_documents(db_session, [document]) is None
    assert "Old name" in document.path
