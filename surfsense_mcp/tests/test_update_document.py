"""surfsense_update_document routes a content replace through the save path.

A content replace must not touch the legacy PUT; it reads the document to learn
its workspace and title, then POSTs the new body to the editor save endpoint,
pinning the title so the save's heading-derived title never renames the note.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import httpx
from mcp.server.fastmcp import FastMCP

from mcp_server.core.client import SurfSenseClient
from mcp_server.features.knowledge_base import document_tools


def _client_recording(calls: list[dict]) -> SurfSenseClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode() or ""
        calls.append(
            {"method": request.method, "path": request.url.path, "body": body}
        )
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": 7,
                    "workspace_id": 3,
                    "title": "Old Title",
                    "document_type": "NOTE",
                },
            )
        return httpx.Response(200, json={"status": "saved", "document_id": 7})

    client = SurfSenseClient(
        api_base="http://test/api/v1", timeout=5, fallback_api_key="ss_pat_x"
    )
    client._http = httpx.AsyncClient(
        base_url="http://test/api/v1",
        headers={"Accept": "application/json"},
        transport=httpx.MockTransport(handler),
    )
    return client


def _call_update(client: SurfSenseClient, **arguments) -> str:
    mcp = FastMCP("test")
    document_tools.register(mcp, client, MagicMock())
    blocks = asyncio.run(mcp.call_tool("surfsense_update_document", arguments))
    return "".join(block.text for block in blocks)


def test_update_saves_the_body_and_pins_the_title():
    calls: list[dict] = []

    _call_update(_client_recording(calls), document_id=7, content="New body")

    get_call, save_call = calls
    assert get_call["method"] == "GET"
    assert get_call["path"] == "/api/v1/documents/7"

    assert save_call["method"] == "POST"
    assert save_call["path"] == "/api/v1/workspaces/3/documents/7/save"
    assert json.loads(save_call["body"]) == {
        "source_markdown": "New body",
        "title": "Old Title",
    }
