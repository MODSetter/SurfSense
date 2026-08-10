from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.artifacts import service
from app.artifacts.service import ArtifactFileInput, save_artifact
from app.file_storage.persistence.models import DocumentFile
from app.routes import document_files_routes, editor_routes

from .test_service import MemoryBackend

pytestmark = pytest.mark.integration


@pytest.fixture
def editor_artifacts(monkeypatch):
    backend = MemoryBackend()
    monkeypatch.setattr(service, "get_storage_backend", lambda *_: backend)
    monkeypatch.setattr(
        service, "knowledge_store_enabled_for", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(service, "_index_legacy", AsyncMock())
    monkeypatch.setattr(editor_routes, "check_permission", AsyncMock())
    monkeypatch.setattr(document_files_routes, "check_permission", AsyncMock())
    return backend


async def test_markdown_artifact_returns_read_only_text_contract(
    db_session, db_workspace, editor_artifacts
):
    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=1,
        tool_call_id="text",
        title="Markdown",
        markdown_representation="# Markdown",
        files=[],
    )

    response = await editor_routes.get_editor_content(
        db_workspace.id, saved.document_id, db_session, object()
    )

    assert response["kind"] == "text"
    assert response["generated"] is True
    assert response["source_markdown"] == "# Markdown"


async def test_seeded_pdf_returns_file_contract(
    db_session, db_workspace, editor_artifacts
):
    saved = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=1,
        tool_call_id="pdf",
        title="PDF",
        markdown_representation="# PDF summary",
        files=[
            ArtifactFileInput(
                data=b"%PDF",
                filename="document.pdf",
                mime_type="application/pdf",
            ),
            ArtifactFileInput(
                data=b"<html></html>",
                filename="source.html",
                mime_type="text/html",
                role="source",
            ),
        ],
    )

    response = await editor_routes.get_editor_content(
        db_workspace.id, saved.document_id, db_session, object()
    )

    assert response == {
        "kind": "file",
        "document_id": saved.document_id,
        "title": "PDF",
        "generated": True,
        "files": [
            {
                "file_id": saved.files[0].file_id,
                "role": "primary",
                "filename": "document.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 4,
                "content_url": (
                    f"/api/v1/workspaces/{db_workspace.id}/documents/"
                    f"{saved.document_id}/files/{saved.files[0].file_id}/content"
                ),
            }
        ],
        "updated_at": response["updated_at"],
    }

    source = await db_session.scalar(
        select(DocumentFile).where(
            DocumentFile.document_id == saved.document_id,
            DocumentFile.role == "source",
        )
    )
    with pytest.raises(HTTPException) as error:
        await document_files_routes.stream_document_file(
            db_workspace.id,
            saved.document_id,
            source.id,
            SimpleNamespace(headers={}),
            db_session,
            object(),
        )
    assert error.value.status_code == 404
