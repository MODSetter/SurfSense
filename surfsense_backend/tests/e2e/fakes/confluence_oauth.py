"""Strict Confluence OAuth fakes for Playwright E2E."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "confluence_pages.json"

_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
_ACCESS_TOKEN = "fake-confluence-access-token"
_REFRESH_TOKEN = "fake-confluence-refresh-token"
_OAUTH_CODE = "fake-confluence-oauth-code"


def _load_fixture() -> dict[str, Any]:
    with _FIXTURE_PATH.open() as f:
        return json.load(f)


_FIXTURE = _load_fixture()


class _StrictFakeMixin:
    _component_name: str = "<unknown>"

    def __getattr__(self, name: str) -> Any:
        raise NotImplementedError(
            f"E2E Confluence OAuth fake missing surface: "
            f"{self._component_name}.{name!r}. "
            "Add it to surfsense_backend/tests/e2e/fakes/confluence_oauth.py."
        )


class _FakeResponse(_StrictFakeMixin):
    _component_name = "httpx.Response"

    def __init__(self, payload: Any, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload, sort_keys=True)

    def json(self) -> Any:
        return self._payload


class _FakeHttpxAsyncClient(_StrictFakeMixin):
    _component_name = "httpx.AsyncClient"

    def __init__(self, *args: Any, **kwargs: Any):
        del args, kwargs

    async def __aenter__(self) -> _FakeHttpxAsyncClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb

    async def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        if url != _TOKEN_URL:
            raise NotImplementedError(f"Unexpected Confluence OAuth POST url={url!r}")

        data = kwargs.get("json") or {}
        headers = kwargs.get("headers") or {}
        if headers.get("Content-Type") != "application/json":
            raise ValueError("Confluence OAuth token exchange expected JSON headers.")

        grant_type = data.get("grant_type")
        if grant_type == "authorization_code":
            if data.get("code") != _OAUTH_CODE:
                raise ValueError(
                    f"Unexpected fake Confluence OAuth code: {data.get('code')!r}"
                )
            if not data.get("client_id") or not data.get("client_secret"):
                raise ValueError("Confluence OAuth token exchange missing client creds.")
            if "/api/v1/auth/confluence/connector/callback" not in str(
                data.get("redirect_uri", "")
            ):
                raise ValueError(
                    "Confluence OAuth token exchange got unexpected redirect_uri: "
                    f"{data.get('redirect_uri')!r}"
                )
        elif grant_type == "refresh_token":
            if data.get("refresh_token") != _REFRESH_TOKEN:
                raise ValueError(
                    "Unexpected fake Confluence refresh token: "
                    f"{data.get('refresh_token')!r}"
                )
        else:
            raise ValueError(f"Unexpected fake Confluence grant_type: {grant_type!r}")

        return _FakeResponse(
            {
                "access_token": _ACCESS_TOKEN,
                "refresh_token": _REFRESH_TOKEN,
                "expires_in": 3600,
                "scope": "read:confluence-user read:space:confluence read:page:confluence",
                "token_type": "Bearer",
            }
        )

    async def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        if url != _RESOURCES_URL:
            raise NotImplementedError(f"Unexpected Confluence OAuth GET url={url!r}")

        headers = kwargs.get("headers") or {}
        auth = headers.get("Authorization")
        if auth != f"Bearer {_ACCESS_TOKEN}":
            raise ValueError(f"Unexpected Confluence resources Authorization: {auth!r}")

        site = _FIXTURE["site"]
        return _FakeResponse(
            [
                {
                    "id": site["cloud_id"],
                    "name": site["name"],
                    "url": site["url"],
                    "scopes": [
                        "read:confluence-user",
                        "read:space:confluence",
                        "read:page:confluence",
                    ],
                }
            ]
        )


class _FakeHttpxModule(_StrictFakeMixin):
    _component_name = "httpx"

    AsyncClient = _FakeHttpxAsyncClient


def install(active_patches: list[Any]) -> None:
    """Patch only Confluence route-local HTTP OAuth calls."""
    p = patch(
        "app.routes.confluence_add_connector_route.httpx",
        _FakeHttpxModule(),
    )
    p.start()
    active_patches.append(p)
