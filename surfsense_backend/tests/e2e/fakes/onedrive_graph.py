"""Strict Microsoft OneDrive Graph fakes for Playwright E2E.

This module patches the OneDrive OAuth route and indexer consumer-site
bindings. It keeps the production add/callback/indexing flow intact while
serving deterministic Microsoft-shaped token, profile, metadata, and file
content responses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx

_ONEDRIVE_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "onedrive_files.json"


def _load_onedrive_fixture() -> dict[str, Any]:
    with _ONEDRIVE_FIXTURE_PATH.open() as f:
        return json.load(f)


_ONEDRIVE_FIXTURE = _load_onedrive_fixture()


class _StrictFakeMixin:
    _component_name: str = "<unknown>"

    def __getattr__(self, name: str) -> Any:
        raise NotImplementedError(
            f"E2E OneDrive fake missing surface: "
            f"{self._component_name}.{name!r}. Add it to "
            f"surfsense_backend/tests/e2e/fakes/onedrive_graph.py."
        )


class _FakeOneDriveClient(_StrictFakeMixin):
    _component_name = "OneDriveClient"

    def __init__(self, session: Any, connector_id: int):
        self._session = session
        self._connector_id = connector_id

    async def list_children(
        self, item_id: str = "root"
    ) -> tuple[list[dict[str, Any]], str | None]:
        items = _ONEDRIVE_FIXTURE.get(item_id)
        if not isinstance(items, list):
            return [], f"E2E OneDrive fake has no children for item_id={item_id!r}."
        return [dict(item) for item in items], None

    async def get_item_metadata(
        self, item_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        metadata = _onedrive_get_metadata(item_id)
        if metadata is None:
            return None, f"E2E OneDrive fake has no metadata for item_id={item_id!r}."
        return metadata, None

    async def download_file(self, item_id: str) -> tuple[bytes | None, str | None]:
        content = _ONEDRIVE_FIXTURE.get("_file_contents", {}).get(item_id)
        if content is None:
            return None, f"E2E OneDrive fake has no content for item_id={item_id!r}."
        return content.encode("utf-8"), None

    async def download_file_to_disk(self, item_id: str, dest_path: str) -> str | None:
        content = _ONEDRIVE_FIXTURE.get("_file_contents", {}).get(item_id)
        if content is None:
            return f"E2E OneDrive fake has no content for item_id={item_id!r}."
        with open(dest_path, "wb") as f:
            f.write(content.encode("utf-8"))
        return None

    async def get_delta(
        self, folder_id: str | None = None, delta_link: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        folder_key = folder_id or "root"
        if delta_link:
            folder_key = delta_link.rsplit("/", 1)[-1].removesuffix("-delta")
        if folder_key not in _ONEDRIVE_FIXTURE:
            return [], None, f"E2E OneDrive fake has no delta for folder={folder_key!r}."
        return [], f"https://graph.microsoft.com/v1.0/fake-delta/{folder_key}-delta", None


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
        if "login.microsoftonline.com" in url and url.endswith("/token"):
            return _json_response(
                "POST",
                url,
                {
                    "access_token": "fake-onedrive-access-token",
                    "refresh_token": "fake-onedrive-refresh-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "offline_access User.Read Files.Read.All Files.ReadWrite.All",
                },
            )
        raise NotImplementedError(f"E2E OneDrive fake unexpected POST URL: {url!r}")

    async def get(self, url: str, *args: Any, **kwargs: Any) -> httpx.Response:
        del args, kwargs
        if url == "https://graph.microsoft.com/v1.0/me":
            return _json_response(
                "GET",
                url,
                {
                    "mail": "onedrive-e2e@surfsense.example",
                    "userPrincipalName": "onedrive-e2e@surfsense.example",
                    "displayName": "SurfSense OneDrive E2E",
                },
            )
        raise NotImplementedError(f"E2E OneDrive fake unexpected GET URL: {url!r}")

    async def request(
        self, method: str, url: str, *args: Any, **kwargs: Any
    ) -> httpx.Response:
        del args, kwargs
        raise NotImplementedError(
            f"E2E OneDrive fake unexpected request: {method!r} {url!r}"
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


def _onedrive_get_metadata(item_id: str | None) -> dict[str, Any] | None:
    for items in _ONEDRIVE_FIXTURE.values():
        if not isinstance(items, list):
            continue
        for entry in items:
            if entry.get("id") == item_id:
                return dict(entry)
    return None


def install(active_patches: list[Any]) -> None:
    """Patch production OneDrive bindings to use strict Graph fakes."""
    targets = [
        ("app.routes.onedrive_add_connector_route.httpx", _FakeHttpxModule()),
        ("app.routes.onedrive_add_connector_route.OneDriveClient", _FakeOneDriveClient),
        ("app.tasks.connector_indexers.onedrive_indexer.OneDriveClient", _FakeOneDriveClient),
        ("app.connectors.onedrive.client.httpx", _FakeHttpxModule()),
    ]
    for target, replacement in targets:
        p = patch(target, replacement)
        p.start()
        active_patches.append(p)
