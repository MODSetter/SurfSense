"""Tests for DropboxClient delta-sync methods (get_latest_cursor, get_changes)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.connectors.dropbox.client import DropboxClient

pytestmark = pytest.mark.unit


def _make_client() -> DropboxClient:
    """Create a DropboxClient with a mocked DB session so no real DB needed."""
    client = DropboxClient.__new__(DropboxClient)
    client._session = MagicMock()
    client._connector_id = 1
    return client


# ---------- C1: get_latest_cursor ----------


async def test_get_latest_cursor_returns_cursor_string(monkeypatch):
    client = _make_client()

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"cursor": "AAHbKxRZ9enq…"}

    monkeypatch.setattr(client, "_request", AsyncMock(return_value=fake_resp))

    cursor, error = await client.get_latest_cursor("/my-folder")

    assert cursor == "AAHbKxRZ9enq…"
    assert error is None
    client._request.assert_called_once_with(
        "/2/files/list_folder/get_latest_cursor",
        {
            "path": "/my-folder",
            "recursive": False,
            "include_non_downloadable_files": True,
        },
    )


# ---------- C2: get_changes returns entries and new cursor ----------


async def test_get_changes_returns_entries_and_cursor(monkeypatch):
    client = _make_client()

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "entries": [
            {".tag": "file", "name": "new.txt", "id": "id:abc"},
            {".tag": "deleted", "name": "old.txt"},
        ],
        "cursor": "cursor-v2",
        "has_more": False,
    }
    monkeypatch.setattr(client, "_request", AsyncMock(return_value=fake_resp))

    entries, new_cursor, error = await client.get_changes("cursor-v1")

    assert error is None
    assert new_cursor == "cursor-v2"
    assert len(entries) == 2
    assert entries[0]["name"] == "new.txt"
    assert entries[1][".tag"] == "deleted"


# ---------- C3: get_changes handles pagination ----------


async def test_get_changes_handles_pagination(monkeypatch):
    client = _make_client()

    page1 = MagicMock()
    page1.status_code = 200
    page1.json.return_value = {
        "entries": [{".tag": "file", "name": "a.txt", "id": "id:a"}],
        "cursor": "cursor-page2",
        "has_more": True,
    }
    page2 = MagicMock()
    page2.status_code = 200
    page2.json.return_value = {
        "entries": [{".tag": "file", "name": "b.txt", "id": "id:b"}],
        "cursor": "cursor-final",
        "has_more": False,
    }

    request_mock = AsyncMock(side_effect=[page1, page2])
    monkeypatch.setattr(client, "_request", request_mock)

    entries, new_cursor, error = await client.get_changes("cursor-v1")

    assert error is None
    assert new_cursor == "cursor-final"
    assert len(entries) == 2
    assert {e["name"] for e in entries} == {"a.txt", "b.txt"}
    assert request_mock.call_count == 2


# ---------- C4: get_changes raises on 401 ----------


async def test_get_changes_returns_error_on_401(monkeypatch):
    client = _make_client()

    fake_resp = MagicMock()
    fake_resp.status_code = 401
    fake_resp.text = "Unauthorized"

    monkeypatch.setattr(client, "_request", AsyncMock(return_value=fake_resp))

    entries, new_cursor, error = await client.get_changes("old-cursor")

    assert error is not None
    assert "401" in error
    assert entries == []
    assert new_cursor is None
