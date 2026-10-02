"""SurfSense's tools as opencode's MCP client reaches them: one route per workspace."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Engine, select

from api.main import create_app
from modules.chunks.models import Chunk
from modules.documents.models import Document, DocumentType
from shared.db import create_session_factory
from worker.ingestion import run

pytestmark = pytest.mark.integration


@dataclass
class ToolEndpoint:
    """The app as opencode's MCP client reaches it, with the key it was launched with."""

    client: AsyncClient
    launch_key: str

    async def workspace(self) -> int:
        """A new workspace, made the way the app makes one."""
        reply = await self.client.post("/workspaces", json={"name": "Research"})
        reply.raise_for_status()
        return reply.json()["id"]

    async def post(
        self, workspace_id: int, message: dict[str, Any], **headers: str
    ) -> Response:
        """One JSON-RPC message, sent with the headers opencode's client sends."""
        return await self.client.post(
            f"/agent/tools/workspaces/{workspace_id}",
            json=message,
            headers={
                "Authorization": f"Bearer {self.launch_key}",
                "Accept": "application/json, text/event-stream",
                **headers,
            },
        )

    async def request(
        self, workspace_id: int, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """A request's JSON-RPC reply."""
        message = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            message["params"] = params
        reply = await self.post(workspace_id, message)
        assert reply.status_code == 200, reply.text
        return reply.json()


def ingest(
    engine: Engine,
    workspace_id: int,
    title: str,
    text: str,
    document_type: DocumentType = DocumentType.NOTE,
) -> tuple[int, int]:
    """A document taken through ingestion to ready: its id and its first chunk's."""
    with create_session_factory(engine)() as session:
        document = Document(
            workspace_id=workspace_id,
            title=title,
            document_type=document_type,
            content=text,
        )
        session.add(document)
        session.commit()
        document_id = document.id
    run(document_id)
    with create_session_factory(engine)() as session:
        chunk_id = session.scalars(
            select(Chunk.id).where(Chunk.document_id == document_id)
        ).first()
    assert chunk_id is not None
    return document_id, chunk_id


@pytest.fixture
async def tools(engine: Engine) -> AsyncIterator[ToolEndpoint]:
    """A fresh app on this test's database, driven in-process."""
    async with _endpoint_over(engine) as endpoint:
        yield endpoint


@asynccontextmanager
async def _endpoint_over(engine: Engine) -> AsyncIterator[ToolEndpoint]:
    """The tool endpoint of a fresh app on `engine`'s database."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield ToolEndpoint(client, app.state.agent_launch_key)


async def test_it_offers_the_search_with_a_flat_schema(tools: ToolEndpoint) -> None:
    """Small local models garble a schema that refers to definitions, so none does."""
    workspace_id = await tools.workspace()

    reply = await tools.request(workspace_id, "tools/list")

    listed = reply["result"]["tools"]
    assert [tool["name"] for tool in listed] == ["search_sources"]
    schema = listed[0]["inputSchema"]
    assert schema["type"] == "object"
    assert schema["required"] == ["query"]
    assert schema["properties"]["query"]["type"] == "string"
    assert not {"$ref", "$defs", "anyOf"} & set(_keys(schema))


def _keys(schema: Any) -> list[str]:
    """Every key anywhere in a JSON value."""
    if isinstance(schema, dict):
        return [k for key, value in schema.items() for k in (key, *_keys(value))]
    if isinstance(schema, list):
        return [k for value in schema for k in _keys(value)]
    return []


async def test_it_agrees_on_the_protocol_opencode_asks_for(tools: ToolEndpoint) -> None:
    """opencode's client offers the newest version it knows and keeps only one it accepts."""
    workspace_id = await tools.workspace()

    reply = await tools.request(
        workspace_id,
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {"roots": {}},
            "clientInfo": {"name": "opencode", "version": "1.18.34"},
        },
    )
    initialized = await tools.post(
        workspace_id, {"jsonrpc": "2.0", "method": "notifications/initialized"}
    )

    assert reply["result"]["protocolVersion"] == "2025-11-25"
    assert "tools" in reply["result"]["capabilities"]
    assert reply["result"]["serverInfo"]["name"] == "SurfSense"
    assert (initialized.status_code, initialized.content) == (202, b"")


async def test_another_protocol_is_answered_with_the_one_spoken(
    tools: ToolEndpoint,
) -> None:
    """Only the version opencode's client asks for is spoken; a client that cannot speak it leaves."""
    workspace_id = await tools.workspace()

    older = await tools.request(
        workspace_id, "initialize", {"protocolVersion": "2025-03-26"}
    )

    assert older["result"]["protocolVersion"] == "2025-11-25"


async def test_only_the_opencode_surfsense_launched_may_call(
    tools: ToolEndpoint,
) -> None:
    """Loopback is open to every process on the machine, and the tools read the user's sources."""
    workspace_id = await tools.workspace()
    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

    reply = await tools.post(workspace_id, listing, Authorization="Bearer stale")

    assert reply.status_code == 401


async def test_a_web_page_is_refused(tools: ToolEndpoint) -> None:
    """A browser names the page's origin; opencode names none (DNS rebinding)."""
    workspace_id = await tools.workspace()
    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

    reply = await tools.post(workspace_id, listing, Origin="http://example.com")

    assert reply.status_code == 403


async def test_no_event_stream_is_offered(tools: ToolEndpoint) -> None:
    """A stream opened here would hang opencode's fallback for its 30 s connect timeout."""
    workspace_id = await tools.workspace()

    reply = await tools.client.get(
        f"/agent/tools/workspaces/{workspace_id}",
        headers={
            "Authorization": f"Bearer {tools.launch_key}",
            "Accept": "text/event-stream",
        },
    )

    assert reply.status_code == 405


async def test_a_search_returns_passages_the_agent_can_cite_and_open(
    tools: ToolEndpoint, engine: Engine, real_model: object
) -> None:
    """Each passage carries the label to cite and the file and lines to read around it."""
    workspace_id = await tools.workspace()
    document_id, chunk_id = ingest(
        engine,
        workspace_id,
        "Plan 2026",
        "# Plan\n\nWe ship on Friday 14 November, after the security review.",
    )

    reply = await tools.request(
        workspace_id,
        "tools/call",
        {"name": "search_sources", "arguments": {"query": "When do we ship?"}},
    )

    result = reply["result"]
    assert result["isError"] is False
    assert result["content"] == [
        {
            "type": "text",
            "text": (
                f'<passage cite="[{chunk_id}]" '
                f'source="sources/Plan 2026 [{document_id}].md" lines="1-3">\n'
                "# Plan\n\nWe ship on Friday 14 November, after the security review.\n"
                "</passage>"
            ),
        }
    ]


async def test_a_search_stays_inside_the_workspaces_sources(
    tools: ToolEndpoint, engine: Engine, real_model: object
) -> None:
    """Another workspace is someone else's research, and an artifact is the agent's own output."""
    workspace_id, elsewhere = await tools.workspace(), await tools.workspace()
    _, own = ingest(engine, workspace_id, "Plan", "We ship on Friday.")
    _, other = ingest(engine, elsewhere, "Plan", "We ship on Monday.")
    _, artifact = ingest(
        engine,
        workspace_id,
        "Summary",
        "We ship on Tuesday.",
        DocumentType.ARTIFACT,
    )

    reply = await tools.request(
        workspace_id,
        "tools/call",
        {"name": "search_sources", "arguments": {"query": "When do we ship?"}},
    )

    text = reply["result"]["content"][0]["text"]
    assert f'cite="[{own}]"' in text
    assert f'cite="[{other}]"' not in text
    assert f'cite="[{artifact}]"' not in text


async def test_a_call_without_a_query_says_what_is_missing(tools: ToolEndpoint) -> None:
    """The model reads the refusal and can call again; a protocol error would end the step."""
    workspace_id = await tools.workspace()

    reply = await tools.request(
        workspace_id, "tools/call", {"name": "search_sources", "arguments": {}}
    )

    assert reply["result"]["isError"] is True
    assert "query" in reply["result"]["content"][0]["text"]


async def test_a_ping_is_answered(tools: ToolEndpoint) -> None:
    """Either side may ask whether the other is still there."""
    workspace_id = await tools.workspace()

    reply = await tools.request(workspace_id, "ping")

    assert reply["result"] == {}


async def test_a_workspace_that_does_not_exist_has_no_tools(
    tools: ToolEndpoint,
) -> None:
    """A deleted workspace's folder may still be registered in a running opencode."""
    reply = await tools.post(404, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert reply.status_code == 404


async def test_a_protocol_this_server_does_not_speak_is_refused(
    tools: ToolEndpoint,
) -> None:
    """A newer client falls back to the handshake on a 400, so the version must be checked."""
    workspace_id = await tools.workspace()
    listing = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

    spoken = await tools.post(
        workspace_id, listing, **{"MCP-Protocol-Version": "2025-11-25"}
    )
    unknown = await tools.post(
        workspace_id, listing, **{"MCP-Protocol-Version": "2031-01-01"}
    )

    assert spoken.status_code == 200
    assert unknown.status_code == 400


async def test_a_search_before_onboarding_says_why_it_cannot_run(
    unlocked_engine: Engine,
) -> None:
    """Until an embedder is chosen nothing is indexed; the model can still grep."""
    async with _endpoint_over(unlocked_engine) as tools:
        workspace_id = await tools.workspace()

        reply = await tools.request(
            workspace_id,
            "tools/call",
            {"name": "search_sources", "arguments": {"query": "When do we ship?"}},
        )

    assert reply["result"]["isError"] is True
    assert "grep" in reply["result"]["content"][0]["text"]
