from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.artifacts import service
from app.artifacts.persistence import Artifact, ArtifactChunk
from app.artifacts.service import ArtifactFileInput, save_artifact
from app.config import config as app_config
from app.db import Document
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.index.converge import index_changes

from .test_service import MemoryBackend

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


async def test_artifact_is_projected_then_indexed_from_git(
    db_session,
    db_workspace,
    knowledge_root,
    patched_embed_texts,
    monkeypatch,
):
    del knowledge_root, patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=True)
    )

    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=44,
        tool_call_id="call-git",
        title="Adoption proof",
        markdown_representation="# Adoption proof\n\nuniquely-searchable-artifact-term",
        files=[
            ArtifactFileInput(b"%PDF-seeded", "proof.pdf", "application/pdf"),
        ],
    )

    artifact = await db_session.get(Artifact, saved.artifact_id)
    assert artifact.path == "/artifacts/Adoption proof.md"
    assert artifact.indexed_generation is None
    assert artifact.indexing_status == "pending"
    assert (
        await db_session.scalar(
            select(func.count(ArtifactChunk.id)).where(
                ArtifactChunk.artifact_id == saved.artifact_id
            )
        )
        == 0
    )

    store = KnowledgeStore.for_workspace(db_workspace.id).with_session(db_session)
    copy = await store.open_turn_copy(44)
    target = copy.path / "artifacts" / "Adoption proof.md"
    assert target.read_text() == "# Adoption proof\n\nuniquely-searchable-artifact-term"

    async def describe(_writes, _removes):
        return "artifacts: save adoption proof"

    await store.commit_turn(
        thread_id=44,
        author_user_id=str(db_workspace.user_id),
        describe=describe,
    )
    projected = await db_session.get(Artifact, saved.artifact_id)
    assert projected.id == saved.artifact_id
    assert projected.indexing_status == "pending"
    assert (
        await db_session.scalar(
            select(func.count(Document.id)).where(
                Document.workspace_id == db_workspace.id
            )
        )
        == 0
    )

    await index_changes(db_session, db_workspace.id)
    await db_session.refresh(projected)
    assert projected.indexed_generation == 1
    assert projected.indexing_status == "ready"
    assert (
        await db_session.scalar(
            select(func.count(ArtifactChunk.id)).where(
                ArtifactChunk.artifact_id == saved.artifact_id,
                ArtifactChunk.content.ilike("%uniquely-searchable-artifact-term%"),
            )
        )
        > 0
    )

    revised = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=44,
        tool_call_id="call-revise",
        title="Renamed proof",
        markdown_representation="# Renamed proof\n\nupdated-artifact-term",
        artifact_id=saved.artifact_id,
        expected_generation=saved.generation,
        files=[
            ArtifactFileInput(b"%PDF-revised", "renamed.pdf", "application/pdf"),
        ],
    )

    assert revised.artifact_id == saved.artifact_id
    assert revised.path == saved.path
    assert revised.generation == 2
    assert revised.title == "Renamed proof"
    assert target.read_text() == "# Renamed proof\n\nupdated-artifact-term"

    await store.commit_turn(
        thread_id=44,
        author_user_id=str(db_workspace.user_id),
        describe=describe,
    )
    await index_changes(db_session, db_workspace.id)
    artifact = await db_session.get(Artifact, saved.artifact_id)
    await db_session.refresh(artifact)
    assert artifact.title == "Renamed proof"
    assert artifact.path == saved.path
    assert artifact.indexed_generation == 2

    copy = await store.open_turn_copy(44)
    target = copy.path / saved.path.removeprefix("/")
    target.unlink()
    await store.commit_turn(
        thread_id=44,
        author_user_id=str(db_workspace.user_id),
        describe=describe,
    )
    await index_changes(db_session, db_workspace.id)

    assert await db_session.get(Artifact, saved.artifact_id) is None
    assert not backend.data
