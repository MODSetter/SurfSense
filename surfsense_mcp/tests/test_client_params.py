"""Unset query params must be omitted, not sent as empty strings."""

from __future__ import annotations

import asyncio

import httpx

from surfsense_mcp.core.client import SurfSenseClient


def _capture(client: SurfSenseClient) -> dict:
    """Swap in a mock transport that records the request it receives."""
    seen: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"ok": True})

    client._http = httpx.AsyncClient(
        base_url="http://test/api/v1", transport=httpx.MockTransport(handler)
    )
    return seen


def test_none_params_are_dropped():
    client = SurfSenseClient(api_base="http://test/api/v1", pat="ss_pat_x", timeout=5)
    seen = _capture(client)
    asyncio.run(
        client.request(
            "GET",
            "/documents",
            params={"workspace_id": 1, "document_types": None, "folder_id": None},
        )
    )
    assert seen["params"] == {"workspace_id": "1"}
    assert "folder_id" not in seen["url"]
