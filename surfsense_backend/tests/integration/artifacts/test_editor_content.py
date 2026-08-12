"""Artifact save contracts no longer depend on legacy document editor rows."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.artifacts import service
from app.artifacts.persistence import Artifact, ArtifactFile, ArtifactFileRole
from app.artifacts.service import ArtifactFileInput, save_artifact

from .test_service import MemoryBackend

pytestmark = pytest.mark.integration


@pytest.fixture
def artifact_backend(monkeypatch):
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(service, "index_artifact", AsyncMock())
    return backend


async def test_markdown_artifact_has_stable_artifact_path(
    db_session, db_workspace, artifact_backend
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
    assert saved.path == "/artifacts/Current _ notes.md"
    assert artifact.search_content == "# Current notes"
    assert artifact.format == "markdown"
    assert saved.files == []


async def test_binary_artifact_exposes_current_non_source_files(
    db_session, db_workspace, artifact_backend
):
    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=1,
        tool_call_id="pdf",
        title="PDF",
        markdown_representation="# PDF summary",
        files=[
            ArtifactFileInput(b"%PDF", "document.pdf", "application/pdf"),
            ArtifactFileInput(
                b"<html></html>", "source.html", "text/html", role="source"
            ),
        ],
    )

    rows = (
        await db_session.scalars(
            select(ArtifactFile).where(ArtifactFile.artifact_id == saved.artifact_id)
        )
    ).all()
    assert {row.role for row in rows} == {
        ArtifactFileRole.PRIMARY,
        ArtifactFileRole.SOURCE,
    }
    assert [file.role for file in saved.files] == ["primary"]
