"""Strict native Google Drive fakes for Playwright E2E.

This module patches the production Google OAuth and Drive SDK bindings used by
the native ``GOOGLE_DRIVE_CONNECTOR`` happy path. It deliberately does not
replace the whole Google package; unmodelled service methods fail loudly.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from google.oauth2.credentials import Credentials

_DRIVE_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "drive_files.json"


def _load_drive_fixture() -> dict[str, Any]:
    with _DRIVE_FIXTURE_PATH.open() as f:
        return json.load(f)


_DRIVE_FIXTURE = _load_drive_fixture()


class _StrictFakeMixin:
    _component_name: str = "<unknown>"

    def __getattr__(self, name: str) -> Any:
        raise NotImplementedError(
            f"E2E native Google Drive fake missing surface: "
            f"{self._component_name}.{name!r}. Add it to "
            f"surfsense_backend/tests/e2e/fakes/native_google_drive.py."
        )


class _FakeFlow(_StrictFakeMixin):
    _component_name = "Flow"

    def __init__(self, *, redirect_uri: str | None = None, scopes: list[str] | None = None):
        self.redirect_uri = redirect_uri
        self.scopes = scopes or []
        self.code_verifier: str | None = None
        self.credentials = _fake_credentials(scopes=self.scopes)

    @classmethod
    def from_client_config(
        cls,
        client_config: dict[str, Any],
        scopes: list[str],
        redirect_uri: str | None = None,
        **_: Any,
    ) -> _FakeFlow:
        del client_config
        return cls(redirect_uri=redirect_uri, scopes=scopes)

    def authorization_url(self, *, state: str, **_: Any) -> tuple[str, str]:
        if not self.redirect_uri:
            raise ValueError("Fake Google Flow requires redirect_uri.")

        parsed = urlparse(self.redirect_uri)
        query = parse_qs(parsed.query)
        query["code"] = ["fake-native-drive-oauth-code"]
        query["state"] = [state]
        redirect = urlunparse(
            parsed._replace(query=urlencode(query, doseq=True))
        )
        return redirect, state

    def fetch_token(self, *, code: str, **_: Any) -> None:
        if code != "fake-native-drive-oauth-code":
            raise ValueError(f"Unexpected fake Google OAuth code: {code!r}")
        self.credentials = _fake_credentials(scopes=self.scopes)


def _fake_credentials(*, scopes: list[str] | None = None) -> Credentials:
    return Credentials(
        token="fake-native-drive-access-token",
        refresh_token="fake-native-drive-refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="fake-native-drive-client-id",
        client_secret="fake-native-drive-client-secret",
        scopes=scopes or ["https://www.googleapis.com/auth/drive"],
        expiry=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
    )


class _FakeRequest(_StrictFakeMixin):
    _component_name = "request"

    def __init__(self, payload: Any):
        self.payload = payload
        self.http = None

    def execute(self, **_: Any) -> Any:
        return self.payload


class _FakeMediaRequest(_StrictFakeMixin):
    _component_name = "media_request"

    def __init__(self, content: bytes):
        self.content = content
        self.http = None


class _FakeMediaIoBaseDownload(_StrictFakeMixin):
    _component_name = "MediaIoBaseDownload"

    def __init__(self, fd, request: _FakeMediaRequest, chunksize: int | None = None):
        del chunksize
        self.fd = fd
        self.request = request
        self._done = False

    def next_chunk(self) -> tuple[None, bool]:
        if not self._done:
            self.fd.write(self.request.content)
            self._done = True
        return None, True


class _FakeDriveFiles(_StrictFakeMixin):
    _component_name = "drive.files"

    def list(self, **kwargs: Any) -> _FakeRequest:
        q = kwargs.get("q", "")
        folder_id = "root"
        if "in parents" in q:
            try:
                folder_id = q.split("'")[1]
            except IndexError:
                folder_id = "root"

        files = _filter_drive_files_for_query(q, _DRIVE_FIXTURE.get(folder_id, []))
        return _FakeRequest({"files": files, "nextPageToken": None})

    def get(self, **kwargs: Any) -> _FakeRequest:
        file_id = kwargs.get("fileId")
        metadata = _drive_get_metadata(file_id)
        return _FakeRequest(metadata)

    def get_media(self, **kwargs: Any) -> _FakeMediaRequest:
        file_id = kwargs.get("fileId")
        content = _DRIVE_FIXTURE.get("_file_contents", {}).get(file_id)
        if content is None:
            raise NotImplementedError(
                f"E2E native Google Drive fake has no content for fileId={file_id!r}."
            )
        return _FakeMediaRequest(content.encode("utf-8"))

    def export(self, **kwargs: Any) -> _FakeRequest:
        file_id = kwargs.get("fileId")
        content = _DRIVE_FIXTURE.get("_file_contents", {}).get(file_id)
        if content is None:
            raise NotImplementedError(
                f"E2E native Google Drive fake has no export content for fileId={file_id!r}."
            )
        return _FakeRequest(content.encode("utf-8"))


class _FakeDriveChanges(_StrictFakeMixin):
    _component_name = "drive.changes"

    def getStartPageToken(self, **_: Any) -> _FakeRequest:  # noqa: N802
        return _FakeRequest({"startPageToken": "fake-native-start-page-token-1"})

    def list(self, **_: Any) -> _FakeRequest:
        return _FakeRequest(
            {"changes": [], "newStartPageToken": "fake-native-start-page-token-1"}
        )


class _FakeDriveService(_StrictFakeMixin):
    _component_name = "drive_service"

    def files(self) -> _FakeDriveFiles:
        return _FakeDriveFiles()

    def changes(self) -> _FakeDriveChanges:
        return _FakeDriveChanges()


class _FakeGmailUsers(_StrictFakeMixin):
    _component_name = "gmail.users"

    def getProfile(self, **kwargs: Any) -> _FakeRequest:  # noqa: N802
        user_id = kwargs.get("userId")
        if user_id != "me":
            raise NotImplementedError(f"Unexpected fake Gmail profile userId={user_id!r}")
        return _FakeRequest({"emailAddress": "native-drive-e2e@surfsense.example"})


class _FakeGmailService(_StrictFakeMixin):
    _component_name = "gmail_service"

    def users(self) -> _FakeGmailUsers:
        return _FakeGmailUsers()


def _fake_build(service_name: str, version: str, **_: Any) -> Any:
    if service_name == "drive" and version == "v3":
        return _FakeDriveService()
    if service_name == "gmail" and version == "v1":
        return _FakeGmailService()
    raise NotImplementedError(
        f"E2E native Google Drive fake cannot build {service_name!r} {version!r}."
    )


def _extract_quoted_value(q: str, anchor: str) -> str | None:
    anchor_idx = q.find(anchor)
    if anchor_idx == -1:
        return None
    after_anchor = q[anchor_idx + len(anchor) :]
    first_quote_idx = after_anchor.find("'")
    if first_quote_idx == -1:
        return None
    after_first_quote = after_anchor[first_quote_idx + 1 :]
    second_quote_idx = after_first_quote.find("'")
    if second_quote_idx == -1:
        return None
    return after_first_quote[:second_quote_idx]


def _filter_drive_files_for_query(q: str, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered = list(files)

    if "trashed = false" in q:
        filtered = [entry for entry in filtered if entry.get("trashed") is not True]

    excluded_mime_type = _extract_quoted_value(q, "mimeType !=")
    if excluded_mime_type:
        filtered = [
            entry for entry in filtered if entry.get("mimeType") != excluded_mime_type
        ]

    included_mime_type = _extract_quoted_value(q, "mimeType =")
    if included_mime_type:
        filtered = [
            entry for entry in filtered if entry.get("mimeType") == included_mime_type
        ]

    return filtered


def _drive_get_metadata(file_id: str | None) -> dict[str, Any]:
    for items in _DRIVE_FIXTURE.values():
        if not isinstance(items, list):
            continue
        for entry in items:
            if entry.get("id") == file_id:
                return dict(entry)
    raise NotImplementedError(
        f"E2E native Google Drive fake has no metadata for fileId={file_id!r}."
    )


def install(active_patches: list[Any]) -> None:
    """Patch production bindings to use native Google Drive fakes."""
    targets = [
        ("app.routes.google_drive_add_connector_route.Flow", _FakeFlow),
        ("app.connectors.google_drive.client.build", _fake_build),
        ("app.connectors.google_gmail_connector.build", _fake_build),
        ("googleapiclient.http.MediaIoBaseDownload", _FakeMediaIoBaseDownload),
        ("app.connectors.google_drive.client._build_thread_http", lambda credentials: None),
    ]
    for target, replacement in targets:
        p = patch(target, replacement)
        p.start()
        active_patches.append(p)

