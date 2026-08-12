from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.artifacts.persistence import ArtifactFileRole
from app.db import Permission
from app.routes import artifacts_routes


def _request(if_none_match: str | None = None) -> Request:
    headers = (
        [(b"if-none-match", if_none_match.encode())] if if_none_match else []
    )
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


@pytest.mark.asyncio
async def test_manifest_is_format_blind_and_hides_source(monkeypatch):
    check = AsyncMock()
    monkeypatch.setattr(artifacts_routes, "check_permission", check)
    artifact = SimpleNamespace(
        id=7,
        title="Workbook",
        format="xlsx",
        generation=3,
        content_hash="hash",
        search_content="# Workbook",
        updated_at=None,
        files=[
            _file(1, ArtifactFileRole.PRIMARY),
            _file(2, ArtifactFileRole.SOURCE),
        ],
    )
    session = AsyncMock()
    session.scalar.return_value = artifact

    result = await artifacts_routes.get_artifact_manifest(
        2, 7, _request(), Response(), session, SimpleNamespace()
    )

    assert result["format"] == "xlsx"
    assert result["markdown_representation"] == "# Workbook"
    assert [file["role"] for file in result["files"]] == ["primary"]
    check.assert_awaited_once()
    assert check.await_args.args[3] == Permission.ARTIFACTS_READ.value


@pytest.mark.asyncio
async def test_manifest_honors_generation_etag(monkeypatch):
    monkeypatch.setattr(artifacts_routes, "check_permission", AsyncMock())
    session = AsyncMock()
    session.scalar.return_value = SimpleNamespace(
        id=7,
        title="Artifact",
        format="markdown",
        generation=3,
        content_hash="hash",
        search_content="body",
        updated_at=None,
        files=[],
    )

    response = await artifacts_routes.get_artifact_manifest(
        2, 7, _request('"hash:3"'), Response(), session, SimpleNamespace()
    )

    assert response.status_code == 304
    assert response.headers["cache-control"] == "private, no-cache"


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
