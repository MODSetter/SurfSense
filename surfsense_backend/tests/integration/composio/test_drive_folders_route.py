from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSourceConnector
from tests.e2e.fakes import composio_module

pytestmark = pytest.mark.integration


async def test_root_listing_returns_canned_items(
    client: httpx.AsyncClient,
    drive_connector: SearchSourceConnector,
):
    response = await client.get(
        f"/api/v1/connectors/{drive_connector.id}/composio-drive/folders"
    )

    assert response.status_code == 200
    items = response.json()["items"]
    names = {item["name"] for item in items}

    assert "Projects" in names
    assert "e2e-canary.txt" in names
    assert any(
        item["id"] == "fake-folder-projects" and item["isFolder"] is True
        for item in items
    )


async def test_save_round_trips_selected_files(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    drive_connector: SearchSourceConnector,
):
    selected_files = [
        {
            "id": "fake-file-canary",
            "name": "e2e-canary.txt",
            "mimeType": "text/plain",
        }
    ]

    response = await client.put(
        f"/api/v1/search-source-connectors/{drive_connector.id}",
        json={
            "config": {
                "selected_folders": [],
                "selected_files": selected_files,
                "indexing_options": {
                    "max_files_per_folder": 10,
                    "incremental_sync": False,
                    "include_subfolders": False,
                },
            }
        },
    )

    assert response.status_code == 200
    await db_session.refresh(drive_connector)
    assert drive_connector.config["selected_files"] == selected_files
    assert drive_connector.config["selected_folders"] == []


async def test_auth_expired_error_classifies_and_flags_connector(
    monkeypatch: pytest.MonkeyPatch,
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    drive_connector: SearchSourceConnector,
):
    def raise_auth_expired(
        self: Any,
        *,
        slug: str,
        connected_account_id: str,
        user_id: str | None = None,
        arguments: dict[str, Any] | None = None,
        dangerously_skip_version_check: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        raise RuntimeError(
            "Token has been expired or revoked. (HTTP 401: invalid_grant)"
        )

    monkeypatch.setattr(composio_module._Tools, "execute", raise_auth_expired)

    response = await client.get(
        f"/api/v1/connectors/{drive_connector.id}/composio-drive/folders"
    )

    assert response.status_code == 400
    body = response.text.lower()
    assert "authentication" in body
    assert "expired" in body

    await db_session.refresh(drive_connector)
    assert drive_connector.config["auth_expired"] is True
