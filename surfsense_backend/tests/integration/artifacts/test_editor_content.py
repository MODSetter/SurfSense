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
        document_files_routes,
        "open_document_file_stream",
        lambda record: backend.open_stream(record.storage_key),
    )
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


async def test_stable_download_resolves_the_latest_file_generation(
    db_session, db_workspace, editor_artifacts
):
    first = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=1,
        tool_call_id="pdf",
        title="Report",
        markdown_representation="# First",
        files=[
            ArtifactFileInput(
                data=b"%PDF-old",
                filename="report.pdf",
                mime_type="application/pdf",
            )
        ],
    )
    revised = await save_artifact(
        db_session,
        workspace_id=db_workspace.id,
        thread_id=1,
        tool_call_id="docx",
        title="Revised report",
        markdown_representation="# Revised",
        document_id=first.document_id,
        files=[
            ArtifactFileInput(
                data=b"PK-new-docx",
                filename="revised-report.docx",
                mime_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
            )
        ],
    )

    response = await document_files_routes.download_current_artifact(
        db_workspace.id,
        first.document_id,
        db_session,
        object(),
    )
    body = b"".join([chunk async for chunk in response.body_iterator])

    assert revised.document_id == first.document_id
    assert revised.files[0].file_id != first.files[0].file_id
    assert body == b"PK-new-docx"
    assert response.media_type.endswith("wordprocessingml.document")
    assert "revised-report.docx" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "private, no-store"


async def test_stable_download_serves_current_text_artifact(
    db_session, db_workspace, editor_artifacts
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

    response = await document_files_routes.download_current_artifact(
        db_workspace.id,
        saved.document_id,
        db_session,
        object(),
    )
    body = b"".join([chunk async for chunk in response.body_iterator])

    assert body == b"# Current notes"
    assert response.media_type == "text/markdown; charset=utf-8"
    assert 'filename="Current _ notes.md"' in response.headers["content-disposition"]
