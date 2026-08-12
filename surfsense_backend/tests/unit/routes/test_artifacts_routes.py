from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.artifacts.persistence import ArtifactFileRole
from app.db import Permission
from app.routes import artifacts_routes


def _request(if_none_match: str | None = None) -> Request:
    headers = [(b"if-none-match", if_none_match.encode())] if if_none_match else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def _file(file_id: int, role: ArtifactFileRole):
    return SimpleNamespace(
        id=file_id,
        role=role,
        original_filename=f"{role.value}.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        storage_backend="local",
        storage_key=f"key-{file_id}",
        checksum_sha256="abc123",
    )


def _row_result(row):
    result = SimpleNamespace(first=lambda: row)
    session = AsyncMock()
    session.execute.return_value = result
    return session


def _rows_result(rows):
    result = SimpleNamespace(all=lambda: rows)
    session = AsyncMock()
    session.execute.return_value = result
    return session


async def _body(response) -> bytes:
    return b"".join([chunk async for chunk in response.body_iterator])


@pytest.mark.asyncio
async def test_manifest_is_format_blind_and_hides_source(monkeypatch):
    check = AsyncMock()
    monkeypatch.setattr(artifacts_routes, "check_permission", check)
    artifact = SimpleNamespace(
        id=7,
        format="xlsx",
        generation=3,
        updated_at=None,
        files=[
            _file(1, ArtifactFileRole.PRIMARY),
            _file(2, ArtifactFileRole.SOURCE),
        ],
    )
    document = SimpleNamespace(
        id=9,
        title="Workbook",
        content_hash="hash",
        source_markdown="# Workbook",
        content="# Workbook",
    )
    session = _row_result((artifact, document))

    result = await artifacts_routes.get_artifact_manifest(
        2, 7, _request(), Response(), session, SimpleNamespace()
    )

    assert result["format"] == "xlsx"
    assert result["document_id"] == 9
    assert result["markdown_representation"] == "# Workbook"
    assert [file["role"] for file in result["files"]] == ["primary"]
    check.assert_awaited_once()
    assert check.await_args.args[3] == Permission.ARTIFACTS_READ.value


@pytest.mark.asyncio
async def test_manifest_honors_generation_etag(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    artifact = SimpleNamespace(
        id=7,
        format="markdown",
        generation=3,
        updated_at=None,
        files=[],
    )
    document = SimpleNamespace(
        id=9,
        title="Artifact",
        content_hash="hash",
        source_markdown="body",
        content="body",
    )
    session = _row_result((artifact, document))

    response = await artifacts_routes.get_artifact_manifest(
        2, 7, _request('"hash:3"'), Response(), session, SimpleNamespace()
    )

    assert response.status_code == 304
    assert response.headers["cache-control"] == "private, no-cache"


@pytest.mark.asyncio
async def test_list_reads_title_and_status_from_document(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    artifact = SimpleNamespace(
        id=7,
        format="pptx",
        generation=2,
        thread_id=11,
        created_at=SimpleNamespace(isoformat=lambda: "created"),
        updated_at=SimpleNamespace(isoformat=lambda: "updated"),
    )
    document = SimpleNamespace(title="Launch deck", status={"state": "processing"})
    session = _rows_result([(artifact, document)])
    response = Response()

    result = await artifacts_routes.list_artifacts(
        2, response, session, SimpleNamespace()
    )

    assert result == [
        {
            "artifact_id": 7,
            "title": "Launch deck",
            "format": "pptx",
            "generation": 2,
            "indexing_status": "processing",
            "thread_id": 11,
            "created_at": "created",
            "updated_at": "updated",
        }
    ]
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_markdown_download_reads_document_body_and_disables_cache(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    artifact = SimpleNamespace(id=7, files=[])
    document = SimpleNamespace(
        title="Current notes", source_markdown="# Current", content=""
    )
    session = _row_result((artifact, document))

    response = await artifacts_routes.download_artifact(
        2, 7, session, SimpleNamespace()
    )

    assert await _body(response) == b"# Current"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-disposition"].startswith("attachment;")


@pytest.mark.asyncio
async def test_current_binary_download_is_attachment_even_for_pdf(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    artifact = SimpleNamespace(id=7, files=[_file(8, ArtifactFileRole.PRIMARY)])
    document = SimpleNamespace(title="PDF", source_markdown="# PDF", content="# PDF")
    session = _row_result((artifact, document))

    async def stream():
        yield b"%PDF"

    monkeypatch.setattr(
        artifacts_routes, "open_artifact_file_stream", lambda _record: stream()
    )
    response = await artifacts_routes.download_artifact(
        2, 7, session, SimpleNamespace()
    )

    assert await _body(response) == b"%PDF"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-disposition"].startswith("attachment;")


@pytest.mark.asyncio
async def test_file_source_is_not_addressable(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    session = AsyncMock()
    session.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        await artifacts_routes.stream_artifact_file(
            2, 7, 8, _request(), session, SimpleNamespace()
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_file_uses_checksum_etag_and_pdf_inline_disposition(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    record = _file(8, ArtifactFileRole.PRIMARY)
    session = AsyncMock()
    session.scalar.return_value = record
    monkeypatch.setattr(
        artifacts_routes,
        "open_artifact_file_stream",
        lambda _record: iter(()),
    )

    response = await artifacts_routes.stream_artifact_file(
        2, 7, 8, _request(), session, SimpleNamespace()
    )

    assert response.headers["etag"] == '"abc123"'
    assert response.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert response.headers["content-disposition"].startswith("inline;")


@pytest.mark.asyncio
async def test_file_honors_checksum_etag(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    session = AsyncMock()
    session.scalar.return_value = _file(8, ArtifactFileRole.PRIMARY)

    response = await artifacts_routes.stream_artifact_file(
        2, 7, 8, _request('"abc123"'), session, SimpleNamespace()
    )

    assert response.status_code == 304


@pytest.mark.asyncio
async def test_delete_marks_joined_document_and_dispatches_document_delete(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    artifact = SimpleNamespace(id=7)
    document = SimpleNamespace(id=9, status={"state": "ready"})
    session = _row_result((artifact, document))
    from app.tasks.celery_tasks import document_tasks

    delay = Mock()
    monkeypatch.setattr(document_tasks.delete_document_task, "delay", delay)

    response = await artifacts_routes.delete_artifact(2, 7, session, SimpleNamespace())

    assert response.status_code == 204
    assert document.status == {"state": "deleting"}
    session.commit.assert_awaited_once()
    delay.assert_called_once_with(9)
