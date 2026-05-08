"""Strict Dropbox HTTP/API fakes for Playwright E2E.

This module patches the Dropbox OAuth route and indexer consumer-site
bindings. It keeps the production add/callback/indexing flow intact while
serving deterministic Dropbox-shaped token, profile, metadata, and file
content responses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx

from .binary_loader import _resolve_file_bytes

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_DROPBOX_FIXTURE_PATH = _FIXTURES_DIR / "dropbox_files.json"


def _load_dropbox_fixture() -> dict[str, Any]:
    with _DROPBOX_FIXTURE_PATH.open() as f:
        return json.load(f)


_DROPBOX_FIXTURE = _load_dropbox_fixture()


class _StrictFakeMixin:
    _component_name: str = "<unknown>"

    def __getattr__(self, name: str) -> Any:
        raise NotImplementedError(
            f"E2E Dropbox fake missing surface: "
            f"{self._component_name}.{name!r}. Add it to "
            f"surfsense_backend/tests/e2e/fakes/dropbox_api.py."
        )


class _FakeDropboxClient(_StrictFakeMixin):
    _component_name = "DropboxClient"

    def __init__(self, session: Any, connector_id: int):
        self._session = session
        self._connector_id = connector_id

    async def _get_valid_token(self) -> str:
        return "fake-dropbox-access-token"

    async def list_folder(
        self, path: str = ""
    ) -> tuple[list[dict[str, Any]], str | None]:
        items = _DROPBOX_FIXTURE.get(path)
        if not isinstance(items, list):
            return [], f"E2E Dropbox fake has no folder for path={path!r}."
        return [dict(item) for item in items], None

    async def get_latest_cursor(self, path: str = "") -> tuple[str | None, str | None]:
        if path not in _DROPBOX_FIXTURE:
            return None, f"E2E Dropbox fake has no cursor for path={path!r}."
        return f"fake-dropbox-cursor:{path or 'root'}", None

    async def get_changes(
        self, cursor: str
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        return [], cursor, None

    async def get_metadata(self, path: str) -> tuple[dict[str, Any] | None, str | None]:
        metadata = _dropbox_get_metadata(path)
        if metadata is None:
            return None, f"E2E Dropbox fake has no metadata for path={path!r}."
        return metadata, None

    async def download_file(self, path: str) -> tuple[bytes | None, str | None]:
        content = _resolve_file_bytes(_DROPBOX_FIXTURE, path, _FIXTURES_DIR)
        if content is None:
            return None, f"E2E Dropbox fake has no content for path={path!r}."
        return content, None

    async def download_file_to_disk(self, path: str, dest_path: str) -> str | None:
        content = _resolve_file_bytes(_DROPBOX_FIXTURE, path, _FIXTURES_DIR)
        if content is None:
            return f"E2E Dropbox fake has no content for path={path!r}."
        with open(dest_path, "wb") as f:
            f.write(content)
        return None

    async def get_current_account(self) -> tuple[dict[str, Any] | None, str | None]:
        return _dropbox_current_account(), None


class _FakeAsyncClient(_StrictFakeMixin):
    _component_name = "httpx.AsyncClient"

    def __init__(self, *args: Any, **kwargs: Any):
        del args, kwargs

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb

    async def post(self, url: str, *args: Any, **kwargs: Any) -> httpx.Response:
        del args, kwargs
        if url == "https://api.dropboxapi.com/oauth2/token":
            return _json_response(
                "POST",
                url,
                {
                    "access_token": "fake-dropbox-access-token",
                    "refresh_token": "fake-dropbox-refresh-token",
                    "token_type": "bearer",
                    "expires_in": 3600,
                    "account_id": "dbid:fake-dropbox-account",
                },
            )
        if url == "https://api.dropboxapi.com/2/users/get_current_account":
            return _json_response("POST", url, _dropbox_current_account())
        raise NotImplementedError(f"E2E Dropbox fake unexpected POST URL: {url!r}")

    async def request(
        self, method: str, url: str, *args: Any, **kwargs: Any
    ) -> httpx.Response:
        del args, kwargs
        raise NotImplementedError(
            f"E2E Dropbox fake unexpected request: {method!r} {url!r}"
        )


class _FakeHttpxModule(_StrictFakeMixin):
    _component_name = "httpx"

    AsyncClient = _FakeAsyncClient


def _json_response(
    method: str, url: str, payload: dict[str, Any], status_code: int = 200
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request(method, url),
    )


def _dropbox_current_account() -> dict[str, Any]:
    return {
        "email": "dropbox-e2e@surfsense.example",
        "name": {"display_name": "SurfSense Dropbox E2E"},
        "account_id": "dbid:fake-dropbox-account",
    }


def _dropbox_get_metadata(path: str | None) -> dict[str, Any] | None:
    for items in _DROPBOX_FIXTURE.values():
        if not isinstance(items, list):
            continue
        for entry in items:
            if entry.get("path_lower") == path or entry.get("id") == path:
                return dict(entry)
    return None


def install(active_patches: list[Any]) -> None:
    """Patch production Dropbox bindings to use strict Dropbox fakes."""
    targets = [
        ("app.routes.dropbox_add_connector_route.httpx", _FakeHttpxModule()),
        ("app.routes.dropbox_add_connector_route.DropboxClient", _FakeDropboxClient),
        (
            "app.tasks.connector_indexers.dropbox_indexer.DropboxClient",
            _FakeDropboxClient,
        ),
        ("app.connectors.dropbox.client.httpx", _FakeHttpxModule()),
    ]
    for target, replacement in targets:
        p = patch(target, replacement)
        p.start()
        active_patches.append(p)
