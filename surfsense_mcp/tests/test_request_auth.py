"""Per-request key resolution and the Authorization header the backend receives.

Covers the security-critical behaviors: the per-request key wins over the env
fallback, the fallback covers stdio, a missing key is refused, and concurrent
callers never see each other's key.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from surfsense_mcp.core.auth import identity
from surfsense_mcp.core.client import SurfSenseClient
from surfsense_mcp.core.errors import ToolError


def _client_recording_auth(seen: dict, *, fallback: str | None) -> SurfSenseClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, json={"ok": True})

    client = SurfSenseClient(
        api_base="http://test/api/v1", timeout=5, fallback_api_key=fallback
    )
    client._http = httpx.AsyncClient(
        base_url="http://test/api/v1", transport=httpx.MockTransport(handler)
    )
    return client


async def _get(client: SurfSenseClient) -> None:
    await client.request("GET", "/workspaces")


def test_request_key_is_sent_as_bearer():
    seen: dict = {}
    client = _client_recording_auth(seen, fallback=None)

    async def run() -> None:
        token = identity.bind_api_key("ss_pat_request")
        try:
            await _get(client)
        finally:
            identity.unbind_api_key(token)

    asyncio.run(run())
    assert seen["authorization"] == "Bearer ss_pat_request"


def test_request_key_overrides_env_fallback():
    seen: dict = {}
    client = _client_recording_auth(seen, fallback="ss_pat_env")

    async def run() -> None:
        token = identity.bind_api_key("ss_pat_request")
        try:
            await _get(client)
        finally:
            identity.unbind_api_key(token)

    asyncio.run(run())
    assert seen["authorization"] == "Bearer ss_pat_request"


def test_env_fallback_used_without_request_key():
    seen: dict = {}
    client = _client_recording_auth(seen, fallback="ss_pat_env")
    asyncio.run(_get(client))
    assert seen["authorization"] == "Bearer ss_pat_env"


def test_missing_key_is_refused():
    client = _client_recording_auth({}, fallback=None)
    with pytest.raises(ToolError):
        asyncio.run(_get(client))


def test_concurrent_callers_do_not_leak_keys():
    seen_by_caller: dict[str, str | None] = {}

    async def call_as(key: str) -> None:
        # Each caller runs in its own task, so the contextvar is isolated.
        recorded: dict = {}
        client = _client_recording_auth(recorded, fallback=None)
        token = identity.bind_api_key(key)
        try:
            await _get(client)
        finally:
            identity.unbind_api_key(token)
        seen_by_caller[key] = recorded["authorization"]

    async def run() -> None:
        await asyncio.gather(call_as("ss_pat_A"), call_as("ss_pat_B"))

    asyncio.run(run())
    assert seen_by_caller["ss_pat_A"] == "Bearer ss_pat_A"
    assert seen_by_caller["ss_pat_B"] == "Bearer ss_pat_B"
