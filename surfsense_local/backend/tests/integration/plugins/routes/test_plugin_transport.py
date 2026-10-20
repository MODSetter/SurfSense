import pytest
from httpx import AsyncClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from tests.mcp_test_server import RequiringHeader, notes_server, serving

pytestmark = pytest.mark.integration


async def test_a_server_offering_only_the_older_sse_transport_connects(
    client: AsyncClient,
) -> None:
    """The 2024-11-05 HTTP+SSE transport, found when a POST is refused, and kept for checks."""
    with serving(notes_server().sse_app()) as base:
        added = await client.post(
            "/plugins/custom", json={"url": f"{base}/sse", "name": "Notes"}
        )
        checked = await client.post("/plugins/notes/check")

    assert added.status_code == 201, added.text
    assert added.json()["transport"] == "sse"
    assert [t["name"] for t in added.json()["tools"]] == ["search", "count"]
    assert checked.json()["check_failure"] is None


async def test_a_streamable_http_server_is_recorded_as_one(
    client: AsyncClient, notes_url: str
) -> None:
    """Today's transport stays the first one tried."""
    added = await client.post(
        "/plugins/custom", json={"url": notes_url, "name": "Notes"}
    )

    assert added.status_code == 201, added.text
    assert added.json()["transport"] == "streamable_http"


async def test_an_sse_servers_headers_reach_it(client: AsyncClient) -> None:
    """A key in a header works the same over the older transport."""
    app = RequiringHeader(notes_server().sse_app(), "x-api-key", "k-1")
    with serving(app) as base:
        added = await client.post(
            "/plugins/custom",
            json={
                "url": f"{base}/sse",
                "name": "Notes",
                "headers": [{"name": "x-api-key", "value": "k-1"}],
            },
        )

    assert added.status_code == 201, added.text
    assert added.json()["transport"] == "sse"


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


async def test_a_web_page_refusing_the_post_and_missing_the_stream_is_refused(
    client: AsyncClient,
) -> None:
    """405 to the POST sends SurfSense to look for SSE; a 404 there is no server either."""

    async def not_allowed(_):
        return Response(status_code=405)

    async def missing(_):
        return Response(status_code=404)

    app = Starlette(
        routes=[
            Route("/mcp", not_allowed, methods=["POST"]),
            Route("/mcp", missing, methods=["GET"]),
        ]
    )
    with serving(app) as base:
        refused = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
        )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_not_mcp"
    assert (await client.get("/plugins")).json() == []


async def test_an_address_its_server_retired_is_said_to_be_gone(
    client: AsyncClient,
) -> None:
    """As DeepWiki's `/sse`: 405 to the POST, then 410 for the stream. Not "not MCP"."""

    async def not_allowed(_):
        return Response(status_code=405)

    async def retired(_):
        return JSONResponse({"error": "SSE transport is deprecated"}, 410)

    app = Starlette(
        routes=[
            Route("/sse", not_allowed, methods=["POST"]),
            Route("/sse", retired, methods=["GET"]),
        ]
    )
    with serving(app) as base:
        refused = await client.post(
            "/plugins/custom", json={"url": f"{base}/sse", "name": "Wiki"}
        )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_gone"
    assert "deprecated" not in refused.text


def _sse_only(stream_status: int) -> Starlette:
    """A server refusing the POST as one with only SSE, and its stream with `stream_status`."""

    async def not_allowed(_):
        return Response(status_code=405)

    async def stream(_):
        return Response(status_code=stream_status)

    return Starlette(
        routes=[
            Route("/sse", not_allowed, methods=["POST"]),
            Route("/sse", stream, methods=["GET"]),
        ]
    )


async def test_an_sse_only_server_needing_a_key_says_so(client: AsyncClient) -> None:
    """Its stream's 401 is the answer, not the POST's 405: the address is right."""
    with serving(_sse_only(401)) as base:
        refused = await client.post(
            "/plugins/custom", json={"url": f"{base}/sse", "name": "Wiki"}
        )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_needs_sign_in"


async def test_an_sse_only_server_that_is_down_says_so(client: AsyncClient) -> None:
    """A 5xx on its stream is a server down, retried first, not an address that is wrong."""
    with serving(_sse_only(503)) as base:
        refused = await client.post(
            "/plugins/custom", json={"url": f"{base}/sse", "name": "Wiki"}
        )

    assert refused.status_code == 502, refused.text
    assert refused.json()["detail"]["code"] == "plugin_unreachable"


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


class _Switching:
    """The notes server on Streamable HTTP, until `older` moves it to SSE only."""

    def __init__(self) -> None:
        notes = notes_server()
        self.streamable = notes.streamable_http_app()
        # The same address, so the plugin's URL is unchanged when it moves.
        self.sse = notes.sse_app(sse_path="/mcp")
        self.older = False

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "lifespan" or not self.older:
            await self.streamable(scope, receive, send)
        else:
            await self.sse(scope, receive, send)


async def test_a_server_that_moved_transport_is_found_again_at_its_check(
    client: AsyncClient,
) -> None:
    """Its recorded transport stopping is not the server going down."""
    app = _Switching()
    with serving(app) as base:
        added = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
        )
        app.older = True
        checked = await client.post("/plugins/notes/check")
        listed = (await client.get("/plugins")).json()[0]

    assert added.json()["transport"] == "streamable_http"
    assert checked.json()["check_failure"] is None
    assert listed["transport"] == "sse"
