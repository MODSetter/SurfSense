"""Postgres converges to the store: real git engine, real Redis lock, real DB.

The indexer's whole job is a projection, so these tests assert on the projection
(rows, ids, chunk ids, the drift stamp) rather than on how it got there.

Paths carry ``.xml`` because that is what every real writer produces —
``safe_filename`` appends it — and the extension is what ``parse_documents_path``
strips to recover a title.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.config import config as app_config
from app.db import Chunk, Document, DocumentStatus, DocumentType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.identities import AGENT_IDENTITY, user_identity
from app.knowledge_store.indexer import PATH_MARKER, index_revision, reindex
from app.utils.document_converters import generate_unique_identifier_hash

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def store(knowledge_root, db_workspace):
    return KnowledgeStore.for_workspace(db_workspace.id)


async def commit(store, writes=None, removes=(), author=None):
    """Record one revision; ``writes`` maps store path to markdown."""
    async with store.transaction(
        message="test", author=author or user_identity("1")
    ) as tx:
        for path, markdown in (writes or {}).items():
            tx.write(path, markdown.encode())
        for path in removes:
            tx.remove(path)
    return tx.revision


async def titles(session, workspace_id) -> dict[str, Document]:
    """Every document in the workspace, keyed by title."""
    result = await session.execute(
        select(Document).where(Document.workspace_id == workspace_id)
    )
    return {document.title: document for document in result.scalars()}


async def chunk_ids(session, document_id) -> list[int]:
    result = await session.execute(
        select(Chunk.id).where(Chunk.document_id == document_id).order_by(Chunk.id)
    )
    return list(result.scalars())


async def chunk_shapes(session, document_id) -> list[tuple]:
    """Text and line span of every chunk, in document order."""
    result = await session.execute(
        select(Chunk.content, Chunk.start_line, Chunk.end_line)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.position)
    )
    return list(result.all())


# ── Identity ────────────────────────────────────────────────────────────────


async def test_identical_content_at_two_paths_yields_two_documents(
    store, db_session, db_workspace, patched_embed_texts
):
    """The case prepare_for_indexing collapses; `cp a b` is legal git."""
    await commit(store, {"documents/a.xml": "# Same", "documents/b.xml": "# Same"})

    await index_revision(db_session, db_workspace.id)

    rows = await titles(db_session, db_workspace.id)
    assert set(rows) == {"a", "b"}
    assert rows["a"].id != rows["b"].id


async def test_uploaded_file_is_adopted_not_duplicated(
    store, db_session, db_workspace, db_user, patched_embed_texts
):
    """An upload already has a row under its own identity; indexing must reuse it."""
    upload = Document(
        title="report.pdf",
        document_type=DocumentType.FILE,
        document_metadata={"FILE_NAME": "report.pdf"},
        content="# Report",
        content_hash=f"hash-{uuid.uuid4().hex}",
        unique_identifier_hash=generate_unique_identifier_hash(
            DocumentType.FILE, "report.pdf", db_workspace.id
        ),
        source_markdown="# Report",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        status=DocumentStatus.ready(),
    )
    db_session.add(upload)
    await db_session.flush()
    upload_id, upload_hash = upload.id, upload.unique_identifier_hash

    await commit(store, {"documents/report.pdf.xml": "# Report"})
    await index_revision(db_session, db_workspace.id)

    total = await db_session.scalar(
        select(func.count(Document.id)).where(Document.workspace_id == db_workspace.id)
    )
    assert total == 1
    await db_session.refresh(upload)
    assert upload.id == upload_id
    # Identity and type stay the upload's; only the location marker is added.
    assert upload.document_type == DocumentType.FILE
    assert upload.unique_identifier_hash == upload_hash
    assert upload.document_metadata[PATH_MARKER] == "/documents/report.pdf.xml"
    assert upload.document_metadata["FILE_NAME"] == "report.pdf"


async def test_existing_path_updates_in_place(
    store, db_session, db_workspace, patched_embed_texts
):
    """A second index of the same path is an update, not a unique-hash collision."""
    await commit(store, {"documents/note.xml": "# First"})
    await index_revision(db_session, db_workspace.id)
    first_id = (await titles(db_session, db_workspace.id))["note"].id

    await commit(store, {"documents/note.xml": "# First\n\nSecond paragraph."})
    await index_revision(db_session, db_workspace.id)

    rows = await titles(db_session, db_workspace.id)
    assert len(rows) == 1
    assert rows["note"].id == first_id
    assert "Second paragraph." in rows["note"].source_markdown


async def test_a_document_in_a_folder_lands_under_that_folder(
    store, db_session, db_workspace, patched_embed_texts
):
    await commit(store, {"documents/Research/paper.xml": "# Paper"})

    await index_revision(db_session, db_workspace.id)

    row = (await titles(db_session, db_workspace.id))["paper"]
    assert row.folder_id is not None
    assert row.document_metadata[PATH_MARKER] == "/documents/Research/paper.xml"


# ── Chunk reuse and removal ─────────────────────────────────────────────────


async def test_editing_one_file_leaves_another_files_chunks_untouched(
    store, db_session, db_workspace, patched_embed_texts
):
    await commit(
        store, {"documents/a.xml": "# A\n\nAlpha.", "documents/b.xml": "# B\n\nBeta."}
    )
    await index_revision(db_session, db_workspace.id)
    untouched = (await titles(db_session, db_workspace.id))["b"]
    before = await chunk_ids(db_session, untouched.id)
    assert before

    await commit(store, {"documents/a.xml": "# A\n\nAlpha, revised."})
    await index_revision(db_session, db_workspace.id)

    assert await chunk_ids(db_session, untouched.id) == before


async def test_removed_path_deletes_the_document_and_its_chunks(
    store, db_session, db_workspace, patched_embed_texts
):
    await commit(store, {"documents/a.xml": "# A", "documents/b.xml": "# B"})
    await index_revision(db_session, db_workspace.id)
    doomed_id = (await titles(db_session, db_workspace.id))["a"].id
    assert await chunk_ids(db_session, doomed_id)

    await commit(store, removes=["documents/a.xml"])
    await index_revision(db_session, db_workspace.id)

    assert set(await titles(db_session, db_workspace.id)) == {"b"}
    assert await chunk_ids(db_session, doomed_id) == []


async def test_a_rename_leaves_exactly_one_document(
    store, db_session, db_workspace, patched_embed_texts
):
    """Git reports a rename as add+delete, so both halves must be applied."""
    await commit(store, {"documents/old.xml": "# Content"})
    await index_revision(db_session, db_workspace.id)

    await commit(
        store, {"documents/new.xml": "# Content"}, removes=["documents/old.xml"]
    )
    await index_revision(db_session, db_workspace.id)

    assert set(await titles(db_session, db_workspace.id)) == {"new"}


# ── Convergence ─────────────────────────────────────────────────────────────


async def test_reindex_keeps_document_ids(
    store, db_session, db_workspace, patched_embed_texts
):
    """Rebuild replaces chunks, never document rows: their ids reach the browser."""
    await commit(store, {"documents/a.xml": "# A", "documents/notes/b.xml": "# B"})
    await index_revision(db_session, db_workspace.id)
    before = {t: d.id for t, d in (await titles(db_session, db_workspace.id)).items()}

    await reindex(db_session, db_workspace.id)

    after = {t: d.id for t, d in (await titles(db_session, db_workspace.id)).items()}
    assert after == before


async def test_reindex_reaches_the_same_state_as_the_incremental_path(
    store, db_session, db_workspace, patched_embed_texts
):
    await commit(store, {"documents/a.xml": "# A", "documents/b.xml": "# B"})
    await index_revision(db_session, db_workspace.id)
    await commit(
        store, {"documents/b.xml": "# B\n\nEdited."}, removes=["documents/a.xml"]
    )
    await index_revision(db_session, db_workspace.id)
    incremental = {
        title: document.source_markdown
        for title, document in (await titles(db_session, db_workspace.id)).items()
    }

    await reindex(db_session, db_workspace.id)

    rebuilt = {
        title: document.source_markdown
        for title, document in (await titles(db_session, db_workspace.id)).items()
    }
    assert rebuilt == incremental


async def test_indexing_a_stamped_revision_does_nothing(
    store, db_session, db_workspace, patched_embed_texts
):
    await commit(store, {"documents/a.xml": "# A"})
    await index_revision(db_session, db_workspace.id)
    calls = patched_embed_texts.call_count

    outcome = await index_revision(db_session, db_workspace.id)

    assert outcome.indexed == 0
    assert patched_embed_texts.call_count == calls


async def test_a_missed_revision_is_folded_in_by_the_next_run(
    store, db_session, db_workspace, patched_embed_texts
):
    """A dropped task must not strand its revision: the next run converges both."""
    await commit(store, {"documents/a.xml": "# A"})
    await commit(store, {"documents/b.xml": "# B"})  # no index run for this one

    await index_revision(db_session, db_workspace.id)

    assert set(await titles(db_session, db_workspace.id)) == {"a", "b"}
    await db_session.refresh(db_workspace)
    assert db_workspace.last_indexed_revision == await store.get_current_revision()


async def test_a_connector_document_survives_a_rebuild(
    store, db_session, db_workspace, db_user, patched_embed_texts
):
    """Prune is keyed on the ownership marker; connector rows have no path at all."""
    connector_row = Document(
        title="Slack thread",
        document_type=DocumentType.SLACK_CONNECTOR,
        document_metadata={"channel": "general"},
        content="Hello",
        content_hash=f"hash-{uuid.uuid4().hex}",
        unique_identifier_hash=f"unique-{uuid.uuid4().hex}",
        source_markdown="Hello",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        status=DocumentStatus.ready(),
    )
    db_session.add(connector_row)
    await db_session.flush()

    await commit(store, {"documents/a.xml": "# A"})
    await reindex(db_session, db_workspace.id)

    assert "Slack thread" in await titles(db_session, db_workspace.id)


async def test_a_rebuild_prunes_a_row_whose_file_is_gone(
    store, db_session, db_workspace, patched_embed_texts
):
    """The rebuild path has no change list, so the tree is the only authority."""
    await commit(store, {"documents/a.xml": "# A", "documents/b.xml": "# B"})
    await index_revision(db_session, db_workspace.id)

    # Remove the file without letting the incremental path see the removal.
    await commit(store, removes=["documents/a.xml"])
    await reindex(db_session, db_workspace.id)

    assert set(await titles(db_session, db_workspace.id)) == {"b"}


# ── Authorship, skips, failures ─────────────────────────────────────────────


async def test_an_agent_authored_revision_falls_back_to_the_workspace_owner(
    store, db_session, db_workspace, db_user, patched_embed_texts
):
    """Autonomous writes carry no user id, and created_by_id rejects blanks."""
    await commit(
        store, {"documents/agent.xml": "# Written by the agent"}, author=AGENT_IDENTITY
    )

    await index_revision(db_session, db_workspace.id)

    assert (await titles(db_session, db_workspace.id))["agent"].created_by_id == (
        db_user.id
    )


async def test_unusable_blobs_are_skipped_and_the_stamp_still_advances(
    store, db_session, db_workspace, patched_embed_texts
):
    """A touched file and a binary are legal git; neither may wedge the workspace."""
    async with store.transaction(message="mixed", author=user_identity("1")) as tx:
        tx.write("documents/good.xml", b"# Good")
        tx.write("documents/blank.xml", b"   \n\n")
        tx.write("documents/binary.xml", b"\xff\xfe\x00\x01")
    revision = tx.revision

    outcome = await index_revision(db_session, db_workspace.id)

    assert set(await titles(db_session, db_workspace.id)) == {"good"}
    assert (outcome.indexed, outcome.skipped) == (1, 2)
    await db_session.refresh(db_workspace)
    assert db_workspace.last_indexed_revision == revision


async def test_the_git_path_chunks_identically_to_the_connector_path(
    store, db_session, db_workspace, db_user, patched_embed_texts
):
    """Differential, not a golden baseline: a baseline rots on the first re-chunk.

    This is also the only assertion that the shared chunk/cache/reconcile chain —
    which ships to every workspace, flag or no flag — still produces the same
    chunks and the same line spans it did for connectors.
    """
    markdown = (
        "# Report\n"
        "\n"
        "First paragraph with some detail.\n"
        "\n"
        "| col | val |\n"
        "| --- | --- |\n"
        "| a   | 1   |\n"
        "\n"
        "Closing paragraph.\n"
    )
    through_connector = Document(
        title="Report via connector",
        document_type=DocumentType.SLACK_CONNECTOR,
        document_metadata={},
        content=markdown,
        content_hash=f"hash-{uuid.uuid4().hex}",
        unique_identifier_hash=f"unique-{uuid.uuid4().hex}",
        source_markdown=markdown,
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        status=DocumentStatus.pending(),
    )
    db_session.add(through_connector)
    await db_session.flush()
    await IndexingPipelineService(db_session).index(
        through_connector,
        ConnectorDocument(
            title=through_connector.title,
            source_markdown=markdown,
            unique_id="slack-1",
            document_type=DocumentType.SLACK_CONNECTOR,
            workspace_id=db_workspace.id,
            created_by_id=str(db_user.id),
        ),
    )

    await commit(store, {"documents/Report.xml": markdown})
    await index_revision(db_session, db_workspace.id)
    through_git = (await titles(db_session, db_workspace.id))["Report"]

    assert await chunk_shapes(db_session, through_git.id) == await chunk_shapes(
        db_session, through_connector.id
    )


async def test_a_failed_document_withholds_the_stamp(
    store, db_session, db_workspace, patched_embed_texts_raises
):
    """Without this the sweep has nothing to retry and the gap is permanent."""
    await commit(store, {"documents/a.xml": "# A"})

    outcome = await index_revision(db_session, db_workspace.id)

    assert outcome.failed == 1
    assert outcome.stamped is False
    await db_session.refresh(db_workspace)
    assert db_workspace.last_indexed_revision is None
