import pytest
from mcp.server.lowlevel.server import Server
from mcp_types import ListToolsResult, Tool

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.mcp_client.session import McpSession
from modules.plugins.remote.source import RemoteMcpSource
from tests.mcp_test_server import FailingFirst, RecordingHeaders, notes_server, serving

pytestmark = pytest.mark.unit


async def listed(url: str, headers: dict[str, str] | None = None) -> list:
    """The tools a server at `url` lists, through one session."""
    session = McpSession(url, headers)
    try:
        return await session.list_tools()
    finally:
        await session.close()


async def test_lists_the_tools_a_server_offers() -> None:
    """Each tool keeps its name, description, input schema and annotations."""
    with serving(notes_server().streamable_http_app()) as base:
        tools = await listed(f"{base}/mcp")

    assert [tool.name for tool in tools] == ["search", "count"]
    assert tools[0].description == "Search the notes."
    assert tools[0].input_schema["properties"]["query"]["type"] == "string"
    assert tools[0].annotations["readOnlyHint"] is True


def paged_server() -> Server:
    """Two pages of tools, the second reached by the first page's cursor."""
    pages = {
        None: (["first"], "page-2"),
        "page-2": (["second"], None),
    }

    async def list_tools(ctx, params):
        names, next_cursor = pages[params.cursor if params else None]
        tools = [Tool(name=name, input_schema={"type": "object"}) for name in names]
        return ListToolsResult(tools=tools, next_cursor=next_cursor)

    return Server("paged", on_list_tools=list_tools)


async def test_lists_every_page_of_tools() -> None:
    """A paged listing is followed to its last page, so no tool is missed."""
    with serving(paged_server().streamable_http_app()) as base:
        tools = await listed(f"{base}/mcp")

    assert [tool.name for tool in tools] == ["first", "second"]


async def test_a_server_that_answers_in_json_works_too() -> None:
    """Servers may answer in JSON instead of SSE; both are Streamable HTTP."""
    with serving(notes_server().streamable_http_app(json_response=True)) as base:
        tools = await listed(f"{base}/mcp")

    assert [tool.name for tool in tools] == ["search", "count"]


async def test_sends_the_plugins_credentials_on_every_request() -> None:
    """The token goes with every request of a listing, the handshake included."""
    app = RecordingHeaders(notes_server().streamable_http_app())
    with serving(app) as base:
        await listed(f"{base}/mcp", {"authorization": "Bearer k-123"})

    assert len(app.authorizations) >= 2
    assert set(app.authorizations) == {"Bearer k-123"}


async def test_listing_is_retried_twice_when_the_server_is_briefly_down() -> None:
    """Listing changes nothing on the server, so a brief outage is ridden out."""
    app = FailingFirst(notes_server().streamable_http_app(), "tools/list", times=2)
    with serving(app) as base:
        tools = await listed(f"{base}/mcp")

    assert len(tools) == 2
    assert app.seen == 3


async def test_a_server_that_keeps_failing_is_refused_with_its_status() -> None:
    """After the retries, the status the server answered says what went wrong."""
    app = FailingFirst(notes_server().streamable_http_app(), "tools/list", times=9)
    with serving(app) as base, pytest.raises(ServerError, match="503") as refused:
        await listed(f"{base}/mcp")

    assert refused.value.status == 503


async def test_a_session_the_server_forgot_is_started_again() -> None:
    """A 2025 server's 404 means it never handled the request, so it is safe to resend.

    The newer protocol has no sessions; this server refuses its opening request, as
    servers still on the 2025 protocol do, so the client falls back to a session.
    """
    on_2025_protocol = FailingFirst(
        notes_server().streamable_http_app(), "server/discover", times=99, status=400
    )
    app = FailingFirst(on_2025_protocol, "tools/list", times=1, status=404)
    with serving(app) as base:
        tools = await listed(f"{base}/mcp")

    assert [tool.name for tool in tools] == ["search", "count"]


async def test_a_remote_plugin_lists_its_tools_as_the_gateway_records_them() -> None:
    """The gateway sees a remote server's tools only as `SourceTool`s."""
    with serving(notes_server().streamable_http_app()) as base:
        source = RemoteMcpSource(f"{base}/mcp")
        try:
            tools = await source.list_tools()
        finally:
            await source.close()

    assert isinstance(tools[0], SourceTool)
    assert tools[0].annotations["readOnlyHint"] is True
