"""surfsense_get_document round-trips through the real tool registration.

The markdown form must ask the backend for the OKF concept via content
negotiation (``Accept: text/markdown``) and pass it through untouched; the JSON
form must leave the default ``application/json`` Accept in place. This is the
only coverage of the MCP-side glue that forwards the header.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import httpx
from mcp.server.fastmcp import FastMCP

from mcp_server.core.client import SurfSenseClient
from mcp_server.features.knowledge_base import search_tools

_CONCEPT = "---\ntype: Note\ntitle: T\n---\n\nBody."


def _client_recording(seen: dict) -> SurfSenseClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["accept"] = request.headers.get("accept")
        if "text/markdown" in (seen["accept"] or ""):
            return httpx.Response(
                200, text=_CONCEPT, headers={"content-type": "text/markdown"}
            )
        return httpx.Response(200, json={"id": 1, "title": "T"})

    client = SurfSenseClient(
        api_base="http://test/api/v1", timeout=5, fallback_api_key="ss_pat_x"
    )
    client._http = httpx.AsyncClient(
        base_url="http://test/api/v1",
        headers={"Accept": "application/json"},
        transport=httpx.MockTransport(handler),
    )
    return client


def _call_get_document(client: SurfSenseClient, **arguments) -> str:
    mcp = FastMCP("test")
    search_tools.register(mcp, client, MagicMock())
    blocks = asyncio.run(mcp.call_tool("surfsense_get_document", arguments))
    return "".join(block.text for block in blocks)


def test_markdown_requests_okf_concept_and_passes_it_through():
    seen: dict = {}
    text = _call_get_document(_client_recording(seen), document_id=1)

    assert seen["path"] == "/api/v1/documents/1"
    assert "text/markdown" in seen["accept"]
    assert text == _CONCEPT


def test_json_keeps_default_accept():
    seen: dict = {}
    text = _call_get_document(
        _client_recording(seen), document_id=1, response_format="json"
    )

    assert seen["path"] == "/api/v1/documents/1"
    assert seen["accept"] == "application/json"
    assert '"id": 1' in text
