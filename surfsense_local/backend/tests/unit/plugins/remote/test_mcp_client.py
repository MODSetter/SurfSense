import threading

import anyio
import pytest
from mcp.server.lowlevel.server import Server
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ListToolsResult, Tool, ToolAnnotations

from modules.plugins.gateway.source_result import SourceResult
from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.remote.mcp_client.call_timed_out import CallTimedOutError
from modules.plugins.remote.mcp_client.server_error import ServerError
from modules.plugins.remote.mcp_client.session import McpSession
from modules.plugins.remote.source import RemoteMcpSource
from tests.mcp_test_server import FailingFirst, RecordingHeaders, serving

pytestmark = pytest.mark.unit


def notes_server() -> MCPServer:
    """A notes plugin: a read-only search, a structured count, a slow crawl and a failure."""
    server = MCPServer("notes")

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def search(query: str) -> str:
        """Search the notes."""
        return f"found {query}"

    @server.tool()
    def count(text: str) -> dict[str, int]:
        """Count the words in a text."""
        return {"words": len(text.split())}

    @server.tool()
    async def crawl(pages: int, ctx: Context) -> str:
        """Crawl some pages, reporting each one."""
        for page in range(1, pages + 1):
            await ctx.report_progress(page, pages, f"page {page}")
        return "crawled"

    @server.tool()
    def fail() -> str:
        """Always fails."""
        raise ToolError("the notes are locked")

    return server


async def test_lists_the_tools_a_server_offers() -> None:
    """Each tool keeps its name, description, input schema and annotations."""
    with serving(notes_server().streamable_http_app()) as base:
        session = McpSession(f"{base}/mcp")
        try:
            tools = await session.list_tools()
        finally:
            await session.close()

    assert [tool.name for tool in tools] == ["search", "count", "crawl", "fail"]
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
        session = McpSession(f"{base}/mcp")
        try:
            tools = await session.list_tools()
        finally:
            await session.close()

    assert [tool.name for tool in tools] == ["first", "second"]


async def test_a_call_returns_the_tools_text_and_structured_content() -> None:
    """A model reads the text; the step and Save to Sources use the structured data."""
    with serving(notes_server().streamable_http_app()) as base:
        session = McpSession(f"{base}/mcp")
        try:
            result = await session.call_tool("count", {"text": "one two three"})
        finally:
            await session.close()

    assert result.is_error is False
    assert result.structured == {"words": 3}
    assert '"words": 3' in result.text


async def test_a_server_that_answers_in_json_works_too() -> None:
    """Servers may answer in JSON instead of SSE; both are Streamable HTTP."""
    app = notes_server().streamable_http_app(json_response=True)
    with serving(app) as base:
        session = McpSession(f"{base}/mcp")
        try:
            tools = await session.list_tools()
            result = await session.call_tool("count", {"text": "a b"})
        finally:
            await session.close()

    assert len(tools) == 4
    assert result.structured == {"words": 2}


async def test_a_tool_that_fails_comes_back_as_a_result_not_an_error() -> None:
    """A tool failing is the server answering, so the model gets the reason to read."""
    with serving(notes_server().streamable_http_app()) as base:
        session = McpSession(f"{base}/mcp")
        try:
            result = await session.call_tool("fail", {})
        finally:
            await session.close()

    assert result.is_error is True
    assert "the notes are locked" in result.text


async def test_sends_the_plugins_credentials_on_every_request() -> None:
    """The token goes with initialize, the listing and the call alike."""
    app = RecordingHeaders(notes_server().streamable_http_app())
    with serving(app) as base:
        session = McpSession(f"{base}/mcp", headers={"authorization": "Bearer k-123"})
        try:
            await session.list_tools()
            await session.call_tool("count", {"text": "a"})
        finally:
            await session.close()

    assert len(app.authorizations) >= 4
    assert set(app.authorizations) == {"Bearer k-123"}


async def test_passes_the_servers_progress_up_while_a_call_runs() -> None:
    """A long call shows its progress in the step while it runs."""
    reports = []
    with serving(notes_server().streamable_http_app()) as base:
        session = McpSession(f"{base}/mcp")
        try:
            result = await session.call_tool(
                "crawl", {"pages": 2}, on_progress=reports.append
            )
        finally:
            await session.close()

    assert result.text == "crawled"
    assert [(r.progress, r.total, r.message) for r in reports] == [
        (1, 2, "page 1"),
        (2, 2, "page 2"),
    ]


async def test_a_call_past_its_deadline_is_cancelled_on_the_server() -> None:
    """The caller stops waiting, and the server is told to stop working."""
    cancelled = threading.Event()
    server = MCPServer("slow")

    @server.tool()
    async def wait() -> str:
        """Waits far longer than any caller."""
        try:
            await anyio.sleep(30)
        except anyio.get_cancelled_exc_class():
            cancelled.set()
            raise
        return "done"

    with serving(server.streamable_http_app()) as base:
        session = McpSession(f"{base}/mcp")
        try:
            with pytest.raises(CallTimedOutError):
                await session.call_tool("wait", {}, timeout=0.5)
            assert cancelled.wait(5)
        finally:
            await session.close()


async def test_listing_is_retried_twice_when_the_server_is_briefly_down() -> None:
    """Listing changes nothing on the server, so a brief outage is ridden out."""
    app = FailingFirst(notes_server().streamable_http_app(), "tools/list", times=2)
    with serving(app) as base:
        session = McpSession(f"{base}/mcp")
        try:
            tools = await session.list_tools()
        finally:
            await session.close()

    assert len(tools) == 4
    assert app.seen == 3


async def test_a_call_is_never_retried_since_the_server_may_have_acted() -> None:
    """A failed call may still have acted, so sending it again could act twice."""
    app = FailingFirst(notes_server().streamable_http_app(), "tools/call", times=1)
    with serving(app) as base:
        session = McpSession(f"{base}/mcp")
        try:
            with pytest.raises(ServerError, match="503"):
                await session.call_tool("count", {"text": "a"})
        finally:
            await session.close()

    assert app.seen == 1


async def test_a_session_the_server_forgot_is_started_again() -> None:
    """A 2025 server's 404 means it never handled the call, so it is safe to resend.

    The newer protocol has no sessions; this server refuses its opening request, as
    servers still on the 2025 protocol do, so the client falls back to a session.
    """
    on_2025_protocol = FailingFirst(
        notes_server().streamable_http_app(), "server/discover", times=99, status=400
    )
    app = FailingFirst(on_2025_protocol, "tools/call", times=1, status=404)
    with serving(app) as base:
        session = McpSession(f"{base}/mcp")
        try:
            await session.list_tools()
            result = await session.call_tool("count", {"text": "a b c"})
        finally:
            await session.close()

    assert result.structured == {"words": 3}


async def test_a_remote_plugin_is_a_tool_source_for_the_gateway() -> None:
    """The gateway sees a remote server only through the interface every source shares."""
    with serving(notes_server().streamable_http_app()) as base:
        source = RemoteMcpSource(f"{base}/mcp")
        try:
            tools = await source.list_tools()
            result = await source.call_tool("count", {"text": "a b"}, timeout=5)
        finally:
            await source.close()

    assert isinstance(tools[0], SourceTool)
    assert tools[0].annotations["readOnlyHint"] is True
    assert result == SourceResult(
        text=result.text, structured={"words": 2}, is_error=False
    )
