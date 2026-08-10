from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.artifacts import service
from app.artifacts.service import ArtifactFileInput, save_artifact
from app.config import config as app_config
from app.db import Chunk, Document
from app.file_storage import service as file_storage_service
from app.file_storage.persistence.models import DocumentFile
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.index.converge import index_changes
from app.knowledge_store.paths import PATH_MARKER

from .test_service import MemoryBackend

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


async def _description(_writes, _removes):
    return "docs: save artifact"


async def test_artifact_is_adopted_once_then_deleted_with_its_blob(
    db_session,
    db_workspace,
    db_user,
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
    monkeypatch.setattr(
        "app.knowledge_store.index.queue.enqueue_index", lambda _workspace_id: None
    )

    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=44,
        tool_call_id="call-git",
        title="Adoption proof",
        markdown_representation="# Adoption proof\n\nuniquely-searchable-artifact-term",
        files=[
            ArtifactFileInput(
                b"%PDF-seeded",
                "proof.pdf",
                "application/pdf",
            ),
            ArtifactFileInput(
                b"print('seeded')",
                "proof.py",
                "text/x-python",
                "source",
            ),
        ],
    )
    assert (
        await db_session.scalar(
            select(func.count(Document.id)).where(Document.id == saved.document_id)
        )
        == 1
    )
    uncommitted = await db_session.get(Document, saved.document_id)
    assert PATH_MARKER not in uncommitted.document_metadata
    assert uncommitted.path == "/documents/Adoption proof.md"

    store = KnowledgeStore.for_workspace(db_workspace.id).with_session(db_session)
    outcome = await store.commit_turn(
        thread_id=44,
        author_user_id=str(db_user.id),
        describe=_description,
    )
    assert outcome.revision
    assert (
        await db_session.scalar(
            select(func.count(Document.id)).where(
                Document.workspace_id == db_workspace.id
            )
        )
        == 1
    )
    document = await db_session.get(Document, saved.document_id)
    assert document.document_metadata[PATH_MARKER] == "/documents/Adoption proof.md"

    await index_changes(db_session, db_workspace.id)
    assert (
        await db_session.scalar(
            select(func.count(Chunk.id)).where(
                Chunk.document_id == saved.document_id,
                Chunk.content.ilike("%uniquely-searchable-artifact-term%"),
            )
        )
        > 0
    )
    assert (
        await db_session.scalar(
            select(func.count(Document.id)).where(Document.id == saved.document_id)
        )
        == 1
    )

    await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=44,
        tool_call_id="call-revise",
        title="Renamed proof",
        markdown_representation="# Renamed proof\n\nupdated-artifact-term",
        document_id=saved.document_id,
        files=[
            ArtifactFileInput(
                b"%PDF-revised",
                "renamed-proof.pdf",
                "application/pdf",
            ),
            ArtifactFileInput(
                b"print('revised')",
                "renamed-proof.py",
                "text/x-python",
                "source",
            ),
        ],
    )
    await store.commit_turn(
        thread_id=44,
        author_user_id=str(db_user.id),
        describe=_description,
    )
    document = await db_session.get(Document, saved.document_id)
    await db_session.refresh(document)
    assert document.title == "Renamed proof"
    assert document.document_metadata[PATH_MARKER] == "/documents/Adoption proof.md"

    copy = await store.open_turn_copy(44)
    (copy.path / "documents" / "Adoption proof.md").unlink()
    await store.commit_turn(
        thread_id=44,
        author_user_id=str(db_user.id),
        describe=_description,
    )
    await index_changes(db_session, db_workspace.id)

    assert await db_session.get(Document, saved.document_id) is None
    assert (
        await db_session.scalar(
            select(func.count(DocumentFile.id)).where(
                DocumentFile.document_id == saved.document_id
            )
        )
        == 0
    )
    assert not backend.data
