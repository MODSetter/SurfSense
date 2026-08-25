import contextlib
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts import service
from app.artifacts.persistence import Artifact
from app.artifacts.service import ArtifactFileInput, save_artifact
from app.config import config as app_config
from app.db import Chunk, Document, DocumentStatus, DocumentType
from app.file_storage import service as file_storage_service
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.index.converge import index_changes, index_tree
from app.knowledge_store.paths import to_store_path

from .test_service import MemoryBackend

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def per_doc_sessions(db_session: AsyncSession, monkeypatch):
    """Bind converge's per-document session to the test's connection.

    Mirrors the knowledge_store suite's harness: converge indexes each document
    in its own session (a separate connection in production), so this test's
    savepoint connection must serve that session too, or the row converge
    committed is invisible and the document never leaves PENDING. Scoped to this
    module, not the artifacts suite — the other artifact tests drive real
    background processing that needs the true separate connection.
    """

    def maker():
        @contextlib.asynccontextmanager
        async def _ctx() -> AsyncIterator[AsyncSession]:
            conn = await db_session.connection()
            async with AsyncSession(
                bind=conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as doc_session:
                yield doc_session

        return _ctx()

    monkeypatch.setattr(
        "app.tasks.celery_tasks.get_celery_session_maker", lambda: maker
    )


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


async def test_artifact_is_projected_then_indexed_from_git(
    db_session,
    db_workspace,
    artifact_thread,
    knowledge_root,
    patched_embed_texts,
    monkeypatch,
):
    del knowledge_root, patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(file_storage_service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=True)
    )

    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id="call-git",
        title="Adoption proof",
        markdown_representation="# Adoption proof\n\nuniquely-searchable-artifact-term",
        files=[
            ArtifactFileInput(b"%PDF-seeded", "proof.pdf", "application/pdf"),
        ],
        committed_by_turn=True,
    )

    artifact = await db_session.get(Artifact, saved.artifact_id)
    document = await db_session.get(Document, artifact.document_id)
    assert document.path == "/documents/Adoption proof.md"
    assert document.document_type == DocumentType.ARTIFACT
    assert DocumentStatus.is_state(document.status, DocumentStatus.PENDING)
    assert (
        await db_session.scalar(
            select(func.count(Chunk.id)).where(Chunk.document_id == document.id)
        )
        == 0
    )

    store = KnowledgeStore.for_workspace(db_workspace.id).with_session(db_session)
    copy = await store.open_turn_copy(artifact_thread.id)
    target = copy.path / "documents" / "Adoption proof.md"
    assert target.read_text() == "# Adoption proof\n\nuniquely-searchable-artifact-term"

    async def describe(_writes, _removes):
        return "artifacts: save adoption proof"

    await store.commit_turn(
        thread_id=artifact_thread.id,
        author_user_id=str(db_workspace.user_id),
        describe=describe,
    )
    projected = await db_session.get(Document, document.id)
    assert projected.id == document.id
    assert projected.document_type == DocumentType.ARTIFACT
    assert DocumentStatus.is_state(projected.status, DocumentStatus.PENDING)
    assert (
        await db_session.scalar(
            select(func.count(Document.id)).where(
                Document.workspace_id == db_workspace.id
            )
        )
        == 1
    )

    await index_changes(db_session, db_workspace.id)
    await db_session.refresh(projected)
    assert projected.document_type == DocumentType.ARTIFACT
    assert DocumentStatus.is_state(projected.status, DocumentStatus.READY)
    assert (
        await db_session.scalar(
            select(func.count(Chunk.id)).where(
                Chunk.document_id == projected.id,
                Chunk.content.ilike("%uniquely-searchable-artifact-term%"),
            )
        )
        > 0
    )
    await index_tree(db_session, db_workspace.id)
    await db_session.refresh(projected)
    assert projected.document_type == DocumentType.ARTIFACT

    revised = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id="call-revise",
        title="Renamed proof",
        markdown_representation="# Renamed proof\n\nupdated-artifact-term",
        artifact_id=saved.artifact_id,
        expected_generation=saved.generation,
        files=[
            ArtifactFileInput(b"%PDF-revised", "renamed.pdf", "application/pdf"),
        ],
        committed_by_turn=True,
    )

    assert revised.artifact_id == saved.artifact_id
    assert revised.generation == 2
    assert revised.title == "Renamed proof"
    assert target.read_text() == "# Renamed proof\n\nupdated-artifact-term"

    await store.commit_turn(
        thread_id=artifact_thread.id,
        author_user_id=str(db_workspace.user_id),
        describe=describe,
    )
    await index_changes(db_session, db_workspace.id)
    artifact = await db_session.get(Artifact, saved.artifact_id)
    document = await db_session.get(Document, artifact.document_id)
    assert document.title == "Renamed proof"
    assert document.path == "/documents/Adoption proof.md"
    assert document.document_type == DocumentType.ARTIFACT

    copy = await store.open_turn_copy(artifact_thread.id)
    target = copy.path / document.path.removeprefix("/")
    target.unlink()
    await store.commit_turn(
        thread_id=artifact_thread.id,
        author_user_id=str(db_workspace.user_id),
        describe=describe,
    )
    await index_changes(db_session, db_workspace.id)
    db_session.expire_all()

    assert await db_session.get(Artifact, saved.artifact_id) is None
    assert not backend.data


async def test_body_is_recorded_when_no_turn_will_commit_it(
    db_session,
    db_workspace,
    artifact_thread,
    knowledge_root,
    patched_embed_texts,
    monkeypatch,
):
    del knowledge_root, patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(file_storage_service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=True)
    )

    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id=None,
        title="Rendered podcast",
        markdown_representation="# Rendered podcast\n\ntranscript",
        files=[ArtifactFileInput(b"ID3-audio", "podcast.mp3", "audio/mpeg")],
    )

    artifact = await db_session.get(Artifact, saved.artifact_id)
    document = await db_session.get(Document, artifact.document_id)
    store = KnowledgeStore.for_workspace(db_workspace.id)
    head = await store.head()

    assert head is not None
    body = await store.read_as_of(head, to_store_path(document.path))
    assert body.decode() == "# Rendered podcast\n\ntranscript"


async def test_two_threads_saving_one_title_get_distinct_paths(
    db_session,
    db_workspace,
    artifact_thread_factory,
    knowledge_root,
    patched_embed_texts,
    monkeypatch,
):
    del knowledge_root, patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(file_storage_service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=True)
    )

    paths = []
    for index in (1, 2):
        thread = await artifact_thread_factory(f"Thread {index}")
        saved = await save_artifact(
            db_session,
            workspace_id=db_workspace.id,
            thread_id=thread.id,
            tool_call_id=f"call-{index}",
            title="Weekly report",
            markdown_representation=f"# Weekly report\n\nrun {index}",
            files=[],
            committed_by_turn=True,
        )
        artifact = await db_session.get(Artifact, saved.artifact_id)
        document = await db_session.get(Document, artifact.document_id)
        paths.append(document.path)

    assert paths == [
        "/documents/Weekly report.md",
        "/documents/Weekly report (2).md",
    ]
