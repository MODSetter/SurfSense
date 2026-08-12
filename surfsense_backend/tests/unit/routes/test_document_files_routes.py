from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routes import document_files_routes


def _request(if_none_match: str | None = None) -> Request:
    headers = []
    if if_none_match:
        headers.append((b"if-none-match", if_none_match.encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def _record(*, mime_type: str = "application/pdf"):
    return SimpleNamespace(
        id=4,
        document_id=3,
        workspace_id=2,
        checksum_sha256="abc123",
        mime_type=mime_type,
        original_filename="résumé.pdf",
        storage_key="key",
    )


@pytest.mark.asyncio
async def test_stream_rejects_cross_workspace_access(monkeypatch):
    denied = HTTPException(status_code=403, detail="denied")
    monkeypatch.setattr(
        document_files_routes, "check_permission", AsyncMock(side_effect=denied)
    )

    with pytest.raises(HTTPException) as exc:
        await document_files_routes.stream_document_file(
            2, 3, 4, _request(), AsyncMock(), SimpleNamespace()
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_stream_returns_404_for_mismatched_file(monkeypatch):
    monkeypatch.setattr(document_files_routes, "check_permission", AsyncMock())
    session = AsyncMock()
    session.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        await document_files_routes.stream_document_file(
            2, 3, 4, _request(), session, SimpleNamespace()
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_stream_honors_etag(monkeypatch):
    monkeypatch.setattr(document_files_routes, "check_permission", AsyncMock())
    session = AsyncMock()
    session.scalar.return_value = _record()

    response = await document_files_routes.stream_document_file(
        2, 3, 4, _request('"abc123"'), session, SimpleNamespace()
    )

    assert response.status_code == 304
    assert response.headers["etag"] == '"abc123"'
    assert response.headers["cache-control"].endswith("immutable")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mime_type", "mode"),
    [
        ("application/pdf", "inline"),
        ("image/png", "attachment"),
        ("text/plain", "attachment"),
        ("text/html", "attachment"),
        ("image/svg+xml", "attachment"),
        ("application/octet-stream", "attachment"),
    ],
)
async def test_stream_disposition_allowlist(monkeypatch, mime_type, mode):
    monkeypatch.setattr(document_files_routes, "check_permission", AsyncMock())
    session = AsyncMock()
    session.scalar.return_value = _record(mime_type=mime_type)

    async def chunks():
        yield b"data"

    monkeypatch.setattr(
        document_files_routes, "open_document_file_stream", lambda _record: chunks()
    )
    response = await document_files_routes.stream_document_file(
        2, 3, 4, _request(), session, SimpleNamespace()
    )

    assert response.headers["content-disposition"].startswith(mode)
    assert (
        "filename*=UTF-8''r%C3%A9sum%C3%A9.pdf"
        in response.headers["content-disposition"]
    )
    assert response.headers["x-content-type-options"] == "nosniff"
