"""Strict Notion OAuth/API fakes for Playwright E2E."""

from __future__ import annotations

import json
import types
from pathlib import Path
from typing import Any
from unittest.mock import patch

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "notion_pages.json"
_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
_ACCESS_TOKEN = "fake-notion-access-token"
_REFRESH_TOKEN = "fake-notion-refresh-token"


def _load_fixture() -> dict[str, Any]:
    with _FIXTURE_PATH.open() as f:
        return json.load(f)


_FIXTURE = _load_fixture()


class _StrictFakeMixin:
    _component_name: str = "<unknown>"

    def __getattr__(self, name: str) -> Any:
        raise NotImplementedError(
            f"E2E Notion fake missing surface: {self._component_name}.{name!r}. "
            "Add it to surfsense_backend/tests/e2e/fakes/notion_module.py."
        )


class APIResponseError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int = 400,
        code: str = "validation_error",
        headers: dict[str, str] | None = None,
        body: Any | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.headers = headers or {}
        self.body = body or {"message": message}


errors = types.ModuleType("notion_client.errors")
errors.APIResponseError = APIResponseError


class _FakeBlocksChildren(_StrictFakeMixin):
    _component_name = "notion.blocks.children"

    async def list(self, **kwargs: Any) -> dict[str, Any]:
        block_id = kwargs.get("block_id")
        start_cursor = kwargs.get("start_cursor")
        if start_cursor is not None:
            raise NotImplementedError(
                f"E2E Notion fake does not model block pagination cursor={start_cursor!r}."
            )

        blocks = _FIXTURE.get("blocks", {}).get(block_id)
        if blocks is None:
            raise APIResponseError(
                f"Could not find block: {block_id}",
                status=404,
                code="object_not_found",
                body={"message": f"Could not find block: {block_id}"},
            )
        return {
            "object": "list",
            "results": blocks,
            "has_more": False,
            "next_cursor": None,
        }


class _FakeBlocks(_StrictFakeMixin):
    _component_name = "notion.blocks"

    def __init__(self) -> None:
        self.children = _FakeBlocksChildren()


class AsyncClient(_StrictFakeMixin):
    _component_name = "notion.AsyncClient"

    def __init__(self, *, auth: str, **kwargs: Any):
        del kwargs
        if auth != _ACCESS_TOKEN:
            raise ValueError(f"Unexpected fake Notion auth token: {auth!r}")
        self.auth = auth
        self.blocks = _FakeBlocks()

    async def search(self, **kwargs: Any) -> dict[str, Any]:
        unsupported = set(kwargs) - {"filter", "sort", "start_cursor"}
        if unsupported:
            raise NotImplementedError(
                f"E2E Notion fake search got unsupported kwargs: {sorted(unsupported)}"
            )
        if kwargs.get("start_cursor") is not None:
            raise NotImplementedError(
                f"E2E Notion fake does not model search cursor={kwargs['start_cursor']!r}."
            )
        expected_filter = {"value": "page", "property": "object"}
        if kwargs.get("filter") != expected_filter:
            raise NotImplementedError(
                f"E2E Notion fake search expected filter={expected_filter!r}, "
                f"got {kwargs.get('filter')!r}."
            )
        return {
            "object": "list",
            "results": _FIXTURE.get("pages", []),
            "has_more": False,
            "next_cursor": None,
        }

    async def aclose(self) -> None:
        return None


class _FakeTokenResponse(_StrictFakeMixin):
    _component_name = "notion.oauth.response"

    def __init__(self, payload: dict[str, Any], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload, sort_keys=True)

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeHttpxAsyncClient(_StrictFakeMixin):
    _component_name = "httpx.AsyncClient"

    async def __aenter__(self) -> _FakeHttpxAsyncClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb

    async def post(self, url: str, **kwargs: Any) -> _FakeTokenResponse:
        if url != _TOKEN_URL:
            raise NotImplementedError(f"Unexpected Notion OAuth POST url={url!r}")

        data = kwargs.get("json") or {}
        headers = kwargs.get("headers") or {}
        if "Authorization" not in headers:
            raise ValueError(
                "Notion OAuth token exchange missing Authorization header."
            )

        grant_type = data.get("grant_type")
        if grant_type == "authorization_code":
            if data.get("code") != "fake-notion-oauth-code":
                raise ValueError(
                    f"Unexpected fake Notion OAuth code: {data.get('code')!r}"
                )
        elif grant_type == "refresh_token":
            if data.get("refresh_token") != _REFRESH_TOKEN:
                raise ValueError(
                    f"Unexpected fake Notion refresh token: {data.get('refresh_token')!r}"
                )
        else:
            raise ValueError(f"Unexpected fake Notion grant_type: {grant_type!r}")

        return _FakeTokenResponse(
            {
                "access_token": _ACCESS_TOKEN,
                "refresh_token": _REFRESH_TOKEN,
                "expires_in": 3600,
                "workspace_id": "fake-notion-workspace-001",
                "workspace_name": "SurfSense E2E Notion Workspace",
                "workspace_icon": "https://surfsense.example/notion-icon.png",
                "bot_id": "fake-notion-bot-001",
            }
        )


def install(active_patches: list[Any]) -> None:
    """Patch production bindings that cannot be covered by sys.modules hijack."""
    targets = [
        (
            "app.routes.notion_add_connector_route.httpx.AsyncClient",
            _FakeHttpxAsyncClient,
        ),
    ]
    for target, replacement in targets:
        p = patch(target, replacement)
        p.start()
        active_patches.append(p)
