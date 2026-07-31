"""Document saves become store revisions (real git engine + real Redis lock)."""

from __future__ import annotations

import uuid

import pytest

from app.agents.chat.runtime.path_resolver import PATH_MARKER
from app.config import config as app_config
from app.db import Document, DocumentStatus, DocumentType
from app.knowledge_store import KnowledgeStore
from app.services import document_revision_recorder as recorder
from app.services.document_revision_recorder import (
    record_markdown_files,
    record_prepared_documents,
    record_saved_document,
)

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
    assert "Meeting notes" in document.document_metadata[PATH_MARKER]


async def test_a_retitle_leaves_only_the_new_path(
    knowledge_root, db_session, db_workspace, db_user, workspace_flip
):
    """The removal has to be derived from the marker, not supplied by the caller."""
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
    assert "New title" in document.document_metadata[PATH_MARKER]


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
    assert document.document_metadata[PATH_MARKER] == "/documents/summary.md"


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
    assert paths == {"documents/Key Points.xml"}
    assert document.document_metadata[PATH_MARKER] == "/documents/Key Points.xml"


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

    async def boom(**kwargs):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(recorder, "record_markdown_files", boom)

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

    async def boom(**kwargs):
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(recorder, "record_markdown_files", boom)

    assert await record_prepared_documents(db_session, [document]) is None
