"""SurfSense speaks Streamable HTTP alone: an `/sse` address, or a server only on the older
SSE, is refused as one, and a plugin recorded on SSE stays as it is until the user replaces it."""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from modules.plugins.installed.models import InstalledPlugin
from shared.db import create_session_factory
from tests.mcp_test_server import notes_server, serving

pytestmark = pytest.mark.integration


async def test_a_server_offering_only_the_older_sse_transport_is_refused_as_one(
    client: AsyncClient,
) -> None:
    """Told what to give instead, rather than that it is no MCP server; nothing is stored."""
    with serving(notes_server().sse_app()) as base:
        refused = await client.post(
            "/plugins/custom", json={"url": f"{base}/sse", "name": "Notes"}
        )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_sse_only"
    assert "/mcp" in refused.json()["detail"]["message"]
    assert (await client.get("/plugins")).json() == []


async def test_an_sse_address_is_refused_without_reaching_its_server(
    client: AsyncClient,
) -> None:
    """Never swapped for its `/mcp`: the user is told, and adds that address themselves."""
    reached: list[str] = []

    async def anything(request):
        reached.append(request.url.path)
        return Response(status_code=404)

    app = Starlette(routes=[Route("/{path:path}", anything, methods=["GET", "POST"])])
    with serving(app) as base:
        refused = await client.post(
            "/plugins/custom", json={"url": f"{base}/sse/", "name": "Notes"}
        )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_sse_only"
    assert reached == []
    assert (await client.get("/plugins")).json() == []


async def test_a_streamable_http_server_is_recorded_as_one(
    client: AsyncClient, notes_url: str
) -> None:
    """The plugin's list says so, as it says a plugin left on SSE."""
    added = await client.post(
        "/plugins/custom", json={"url": notes_url, "name": "Notes"}
    )

    assert added.status_code == 201, added.text
    assert added.json()["transport"] == "streamable_http"


async def test_a_server_answering_neither_transport_is_refused(
    client: AsyncClient,
) -> None:
    """A web page at the address is not an MCP server, and nothing is stored."""

    async def missing(_):
        return Response(status_code=404)

    app = Starlette(routes=[Route("/{path:path}", missing, methods=["GET", "POST"])])
    with serving(app) as base:
        refused = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
        )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_not_mcp"
    assert (await client.get("/plugins")).json() == []


async def test_a_server_down_is_told_apart_from_an_address_that_is_not_mcp(
    client: AsyncClient,
) -> None:
    """Nothing answering is unreachable; a page answering is not an MCP server."""

    async def page(_):
        return Response("<html>Welcome</html>", media_type="text/html")

    app = Starlette(routes=[Route("/mcp", page, methods=["GET", "POST"])])
    with serving(app) as base:
        html = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Page"}
        )
    down = await client.post(
        "/plugins/custom", json={"url": "http://127.0.0.1:9/mcp", "name": "Down"}
    )

    assert html.json()["detail"]["code"] == "plugin_not_mcp", html.text
    assert down.json()["detail"]["code"] == "plugin_unreachable", down.text
    assert "Welcome" not in html.text


def _refusing_the_post(stream: Response) -> Starlette:
    """A server refusing the POST as one without Streamable HTTP, its GET answered with `stream`."""

    async def not_allowed(_):
        return Response(status_code=405)

    async def opened(_):
        return stream

    return Starlette(
        routes=[
            Route("/events", not_allowed, methods=["POST"]),
            Route("/events", opened, methods=["GET"]),
        ]
    )


async def test_a_stream_at_an_address_not_ending_in_sse_is_refused_as_sse(
    client: AsyncClient,
) -> None:
    """Found by the server's own answer: 405 to the POST, an event stream to the GET."""
    stream = Response("", media_type="text/event-stream")
    with serving(_refusing_the_post(stream)) as base:
        refused = await client.post(
            "/plugins/custom", json={"url": f"{base}/events", "name": "Notes"}
        )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_sse_only"


async def test_a_web_page_refusing_the_post_and_missing_the_stream_is_refused(
    client: AsyncClient,
) -> None:
    """405 to the POST and nothing streaming there is no server either."""
    with serving(_refusing_the_post(Response(status_code=404))) as base:
        refused = await client.post(
            "/plugins/custom", json={"url": f"{base}/events", "name": "Notes"}
        )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_not_mcp"


async def test_an_address_its_server_retired_is_said_to_be_gone(
    client: AsyncClient,
) -> None:
    """As DeepWiki's `/sse`: 405 to the POST, then 410 for the stream. Not "not MCP"."""
    retired = JSONResponse({"error": "SSE transport is deprecated"}, 410)
    with serving(_refusing_the_post(retired)) as base:
        refused = await client.post(
            "/plugins/custom", json={"url": f"{base}/events", "name": "Wiki"}
        )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_gone"
    assert "deprecated" not in refused.text


async def test_a_refusal_with_a_json_rpc_body_still_asks_for_a_key(
    client: AsyncClient,
) -> None:
    """Zapier answers 401 with a JSON-RPC error: still a sign-in, and its words stay out."""

    async def refuse(_):
        body = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -31996, "message": "Expected Bearer token SECRET-WORDS"},
        }
        return JSONResponse(body, status_code=401)

    app = Starlette(routes=[Route("/mcp", refuse, methods=["GET", "POST"])])
    with serving(app) as base:
        refused = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
        )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_needs_sign_in"
    assert "SECRET-WORDS" not in refused.text


def _recorded_on_sse(engine: Engine, plugin_id: str, url: str) -> None:
    """As a plugin connected over SSE before this release was recorded."""
    with create_session_factory(engine)() as session:
        plugin = session.get_one(InstalledPlugin, plugin_id)
        plugin.url = url
        plugin.entry = {**plugin.entry, "transport": "sse"}
        session.commit()


async def _added_then_on_sse(client: AsyncClient, engine: Engine, base: str) -> None:
    added = await client.post(
        "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
    )
    assert added.status_code == 201, added.text
    _recorded_on_sse(engine, "notes", f"{base}/sse")


async def test_a_plugin_recorded_on_sse_stays_as_it_is_at_its_check(
    client: AsyncClient, engine: Engine, notes_url: str
) -> None:
    """Never moved behind the user's back, and never contacted: its status says to replace it."""
    await _added_then_on_sse(client, engine, notes_url.removesuffix("/mcp"))
    reached: list[str] = []

    async def anything(request):
        reached.append(request.url.path)
        return Response(status_code=404)

    app = Starlette(routes=[Route("/{path:path}", anything, methods=["GET", "POST"])])
    with serving(app) as old:
        _recorded_on_sse(engine, "notes", f"{old}/sse")
        checked = await client.post("/plugins/notes/check")

        assert checked.status_code == 200, checked.text
        assert checked.json()["transport"] == "sse"
        assert checked.json()["url"] == f"{old}/sse"
    assert reached == []
