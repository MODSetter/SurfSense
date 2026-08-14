from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select

from app.artifacts import service
from app.artifacts.persistence import Artifact, ArtifactFile
from app.artifacts.service import ArtifactFileInput, save_artifact
from app.config import config
from app.db import Chunk, Document, DocumentType
from app.file_storage import service as file_storage_service
from app.file_storage.backends.base import StorageBackend
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.knowledge_store.index.rows import delete_row, prune
from app.knowledge_store.paths import PATH_MARKER

pytestmark = pytest.mark.integration


class MemoryBackend(StorageBackend):
    backend_name = "memory"

    def __init__(self, *, fail_on_put: int | None = None) -> None:
        self.data: dict[str, bytes] = {}
        self.puts = 0
        self.fail_on_put = fail_on_put

    async def put(self, key: str, data: bytes, *, content_type: str | None = None):
        del content_type
        self.puts += 1
        if self.fail_on_put == self.puts:
            raise RuntimeError("forced storage failure")
        self.data[key] = data

    async def delete(self, key: str):
        self.data.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self.data

    async def _stream(self, key: str):
        yield self.data[key]

    def open_stream(self, key: str):
        return self._stream(key)


@pytest.fixture
def artifact_setup(monkeypatch, patched_embed_texts):
    del patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    return backend


async def test_markdown_artifact_payload_and_fences(
    db_session, db_workspace, artifact_thread, artifact_setup
):
    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id="call-1",
        title="Project brief",
        markdown_representation="# Project brief\n\nBody",
        files=[],
    )

    assert saved.status == "saved"
    assert saved.title == "Project brief"
    assert saved.files == []
    artifact = await db_session.get(Artifact, saved.artifact_id)
    document = await db_session.get(Document, artifact.document_id)
    assert artifact.created_by_tool_call_id == "call-1"
    assert artifact.updated_by_tool_call_id == "call-1"
    assert document.title == "Project brief"
    assert document.path == "/documents/Project brief.md"
    assert document.folder_id is None
    assert document.source_markdown == "# Project brief\n\nBody"
    assert document.document_type == DocumentType.ARTIFACT
    assert document.document_metadata == {"artifact_id": artifact.id}
    assert artifact.generation == 1


async def test_binary_create_and_revision_replace_files(
    db_session, db_workspace, artifact_thread, artifact_setup
):
    backend = artifact_setup
    created = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id="call-1",
        title="Seeded PDF",
        markdown_representation="# Seeded PDF",
        files=[
            ArtifactFileInput(
                data=b"old-pdf",
                filename="seeded.pdf",
                mime_type="application/pdf",
            ),
            ArtifactFileInput(
                data=b"old source",
                filename="seeded.py",
                mime_type="text/x-python",
                role="source",
            ),
        ],
        extra_metadata={"verification": {"verified": True, "reason": None}},
    )
    old_rows = (
        await db_session.scalars(
            select(ArtifactFile).where(ArtifactFile.artifact_id == created.artifact_id)
        )
    ).all()
    old_primary = next(row for row in old_rows if row.role == "primary")
    old_keys = {row.storage_key for row in old_rows}

    revised = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id="call-2",
        title="Retitled PDF",
        markdown_representation="# Retitled",
        artifact_id=created.artifact_id,
        expected_generation=created.generation,
        files=[
            ArtifactFileInput(
                data=b"new-pdf",
                filename="retitled.pdf",
                mime_type="application/pdf",
            ),
            ArtifactFileInput(
                data=b"new source",
                filename="retitled.py",
                mime_type="text/x-python",
                role="source",
            ),
        ],
        extra_metadata={
            "verification": {
                "verified": False,
                "reason": "No vision model configured",
            }
        },
    )

    assert revised.artifact_id == created.artifact_id
    assert revised.generation == 2
    assert [file.role for file in revised.files] == ["primary"]
    assert revised.files[0].file_id != old_primary.id
    assert old_keys.isdisjoint(backend.data)
    rows = list(
        (
            await db_session.scalars(
                select(ArtifactFile).where(
                    ArtifactFile.artifact_id == created.artifact_id
                )
            )
        ).all()
    )
    assert {(row.role, row.original_filename) for row in rows} == {
        ("primary", "retitled.pdf"),
        ("source", "retitled.py"),
    }
    artifact = await db_session.get(Artifact, created.artifact_id)
    assert artifact.updated_by_tool_call_id == "call-2"
    assert artifact.artifact_metadata["verification"] == {
        "verified": False,
        "reason": "No vision model configured",
    }


async def test_storage_failure_rolls_back_document_and_blob(
    db_session, db_workspace, artifact_thread, monkeypatch
):
    backend = MemoryBackend(fail_on_put=2)
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )

    with pytest.raises(RuntimeError, match="forced storage failure"):
        await save_artifact(
            db_session,
            workspace_id=db_workspace.id,
            thread_id=artifact_thread.id,
            tool_call_id="call-fail",
            title="Must rollback",
            markdown_representation="# Rollback",
            files=[
                ArtifactFileInput(b"first", "first.pdf", "application/pdf"),
                ArtifactFileInput(
                    b"second", "preview.pdf", "application/pdf", "preview"
                ),
            ],
        )

    assert not backend.data
    assert (
        await db_session.scalar(
            select(func.count(Document.id)).where(Document.title == "Must rollback")
        )
        == 0
    )


async def test_failed_revision_keeps_previous_generation(
    db_session, db_workspace, artifact_thread, artifact_setup, monkeypatch
):
    backend = artifact_setup
    created = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id="call-1",
        title="Stable",
        markdown_representation="# Stable",
        files=[ArtifactFileInput(b"stable", "stable.pdf", "application/pdf")],
    )
    previous_keys = set(backend.data)
    backend.fail_on_put = backend.puts + 2

    with pytest.raises(RuntimeError, match="forced storage failure"):
        await save_artifact(
            db_session,
            workspace_id=db_workspace.id,
            thread_id=artifact_thread.id,
            tool_call_id="call-2",
            title="Broken revision",
            markdown_representation="# Broken",
            artifact_id=created.artifact_id,
            expected_generation=created.generation,
            files=[
                ArtifactFileInput(b"new", "new.pdf", "application/pdf"),
                ArtifactFileInput(
                    b"preview", "preview.pdf", "application/pdf", "preview"
                ),
            ],
        )

    artifact = await db_session.get(Artifact, created.artifact_id)
    await db_session.refresh(artifact)
    document = await db_session.get(Document, artifact.document_id)
    assert document.title == "Stable"
    assert document.source_markdown == "# Stable"
    assert artifact.generation == 1
    assert set(backend.data) == previous_keys
    rows = (
        await db_session.scalars(
            select(ArtifactFile).where(ArtifactFile.artifact_id == created.artifact_id)
        )
    ).all()
    assert [row.original_filename for row in rows] == ["stable.pdf"]


async def test_direct_reindex_preserves_unchanged_chunk_ids(
    db_session, db_workspace, artifact_thread, patched_embed_texts, monkeypatch
):
    del patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    table = "| key | value |\n| --- | --- |\n| stable | chunk |"
    created = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id="call-1",
        title="Incremental",
        markdown_representation=f"# First\n\n{table}\n",
        files=[],
    )
    artifact = await db_session.get(Artifact, created.artifact_id)
    original_table_chunk = await db_session.scalar(
        select(Chunk).where(
            Chunk.document_id == artifact.document_id,
            Chunk.content == table,
        )
    )
    assert original_table_chunk is not None

    await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id="call-2",
        title="Retitled",
        markdown_representation=f"# Revised\n\nNew introduction.\n\n{table}\n",
        artifact_id=created.artifact_id,
        expected_generation=created.generation,
        files=[],
    )

    current_table_chunk = await db_session.scalar(
        select(Chunk).where(
            Chunk.document_id == artifact.document_id,
            Chunk.content == table,
        )
    )
    assert current_table_chunk.id == original_table_chunk.id


async def test_identical_markdown_creates_distinct_artifact_documents(
    db_session, db_workspace, artifact_thread, artifact_setup
):
    first = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id="call-1",
        title="First identity",
        markdown_representation="# Identical",
        files=[],
    )
    second = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id="call-2",
        title="Second identity",
        markdown_representation="# Identical",
        files=[],
    )

    artifacts = list(
        (
            await db_session.scalars(
                select(Artifact).where(
                    Artifact.id.in_([first.artifact_id, second.artifact_id])
                )
            )
        ).all()
    )
    document_ids = {artifact.document_id for artifact in artifacts}
    assert len(document_ids) == 2
    documents = list(
        (
            await db_session.scalars(
                select(Document).where(Document.id.in_(document_ids))
            )
        ).all()
    )
    assert {document.title for document in documents} == {
        "First identity",
        "Second identity",
    }
    assert all(
        document.document_type == DocumentType.ARTIFACT for document in documents
    )
    assert (
        await db_session.scalar(
            select(func.count(Chunk.id)).where(Chunk.document_id.in_(document_ids))
        )
        >= 2
    )


@pytest.mark.parametrize("deletion_path", ["delete", "prune"])
async def test_document_deletion_paths_purge_artifact_blobs(
    db_session,
    db_workspace,
    artifact_thread,
    artifact_setup,
    monkeypatch,
    deletion_path,
):
    backend = artifact_setup
    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=artifact_thread.id,
        tool_call_id=f"call-{deletion_path}",
        title=f"Purge by {deletion_path}",
        markdown_representation="# Purge",
        files=[ArtifactFileInput(b"%PDF", "purge.pdf", "application/pdf")],
    )
    artifact = await db_session.get(Artifact, saved.artifact_id)
    document = await db_session.get(Document, artifact.document_id)
    document_id = document.id
    document.document_metadata = {
        **document.document_metadata,
        PATH_MARKER: document.path,
    }
    await db_session.commit()
    owned = {document.path: document}
    monkeypatch.setattr(file_storage_service, "get_storage_backend", lambda *_: backend)

    if deletion_path == "delete":
        removed = await delete_row(db_session, db_workspace.id, document.path, owned)
        assert removed is document
    else:
        assert await prune(db_session, owned, set()) == 1
    await db_session.commit()
    db_session.expire_all()

    assert not backend.data
    assert await db_session.get(Document, document_id) is None
    assert await db_session.get(Artifact, saved.artifact_id) is None


async def test_non_git_index_failure_keeps_artifact_and_can_be_retried(
    db_session,
    db_workspace,
    artifact_thread,
    patched_embed_texts_raises,
    monkeypatch,
):
    del patched_embed_texts_raises
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    workspace_id = db_workspace.id
    thread_id = artifact_thread.id

    saved = await save_artifact(
        db_session,
        workspace_id=workspace_id,
        thread_id=thread_id,
        tool_call_id="call-failed-index",
        title="Retryable",
        markdown_representation="# Retryable\n\nEmbedding outage",
        files=[],
    )
    artifact = await db_session.get(Artifact, saved.artifact_id)
    document = await db_session.get(Document, artifact.document_id)
    assert document.status["state"] == "failed"

    dimension = config.embedding_model_instance.dimension
    monkeypatch.setattr(
        "app.indexing_pipeline.cache.cached_indexing.embed_texts",
        MagicMock(side_effect=lambda texts: [[0.1] * dimension for _ in texts]),
    )
    await IndexingPipelineService(db_session).index(
        document,
        ConnectorDocument(
            title=document.title,
            source_markdown=document.source_markdown,
            unique_id=document.path,
            document_type=DocumentType.ARTIFACT,
            workspace_id=workspace_id,
            metadata=document.document_metadata,
            created_by_id=str(document.created_by_id),
            folder_id=document.folder_id,
        ),
    )

    await db_session.refresh(document)
    assert document.status["state"] == "ready"
    assert await db_session.scalar(
        select(func.count(Chunk.id)).where(Chunk.document_id == document.id)
    )
