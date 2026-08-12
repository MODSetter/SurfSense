"""Artifact documents can be read by the editor but never saved through it."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.artifacts import service
from app.artifacts.persistence import Artifact
from app.artifacts.service import save_artifact
from app.db import Document, DocumentType
from app.routes import editor_routes

from .test_service import MemoryBackend

pytestmark = pytest.mark.integration


@pytest.fixture
def artifact_backend(monkeypatch, patched_embed_texts):
    del patched_embed_texts
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    return backend


async def test_save_document_rejects_artifact_with_conflict(
    db_session, db_workspace, db_user, artifact_backend, monkeypatch
):
    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=1,
        tool_call_id="markdown",
        title="Current / notes",
        markdown_representation="# Current notes",
        files=[],
    )
    artifact = await db_session.get(Artifact, saved.artifact_id)
    document = await db_session.get(Document, artifact.document_id)
    assert document.document_type == DocumentType.ARTIFACT
    monkeypatch.setattr(editor_routes, "check_permission", AsyncMock())

    with pytest.raises(HTTPException) as exc:
        await editor_routes.save_document(
            db_workspace.id,
            document.id,
            {"source_markdown": "# Mutated outside artifact tools"},
            db_session,
            SimpleNamespace(user=db_user),
        )

    assert exc.value.status_code == 409
    assert "read-only" in exc.value.detail
    await db_session.refresh(document)
    assert document.source_markdown == "# Current notes"
