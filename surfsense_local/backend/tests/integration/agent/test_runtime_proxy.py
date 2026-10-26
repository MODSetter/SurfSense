"""The proxy a runtime reaches the network through: a tunnel to a host it allows, and nothing else.

opencode's allows none; its plugins are reached through the gateway on loopback.
"""

import asyncio
import logging
import socket
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass

import pytest
import pytest_asyncio
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from api.main import create_app, lifespan
from modules.agent.runtime_proxy import allowed_hosts, server
from modules.agent.runtime_proxy.allowed_hosts import AllowedHosts
from modules.agent.runtime_proxy.server import serving_runtime_proxy
from modules.egress.models import EgressDestination
from modules.egress.service import set_enabled
from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.custom_plugin import store_custom_plugin
from modules.plugins.installed.models import PluginTool, ToolApproval
from modules.plugins.installed.third_party import set_third_party_on
from shared.config import get_agent_settings
from shared.db import create_session_factory
from tests.integration.agent.conftest import AgentAPI
from tests.integration.agent.opencode_harness import free_port
from tests.integration.agent.test_agent_threads import of_type, open_thread, send
from tests.mcp_test_server import notes_server, serving

pytestmark = pytest.mark.integration


@dataclass
class Echo:
    """A server that sends back what it is sent, standing in for a host."""

    port: int
    connections: int = 0


@pytest_asyncio.fixture(loop_scope="function")
async def echo() -> AsyncIterator[Echo]:
    """Listens on loopback; a test names it `localhost`, as a remote host's name would."""
    state = Echo(port=0)

    async def answer(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        state.connections += 1
        writer.write(await reader.read(100))
        await writer.drain()
        writer.close()

    echoing = await asyncio.start_server(answer, "127.0.0.1", 0)
    state.port = echoing.sockets[0].getsockname()[1]
    async with echoing:
        yield state


@pytest_asyncio.fixture(loop_scope="function")
async def proxy(engine: Engine) -> AsyncIterator[int]:
    """opencode's proxy on a free loopback port, reading this test's database."""
    async with serving_runtime_proxy(
        create_session_factory(engine), "127.0.0.1", 0
    ) as port:
        yield port


class _Fixed(AllowedHosts):
    """A proxy letting a fixed list through, as Claude Code's lets Anthropic's hosts."""

    def __init__(self, engine: Engine, hosts: set[tuple[str, int]]) -> None:
        super().__init__(create_session_factory(engine))
        self._hosts = frozenset(hosts)

    def _ready(self, session: Session) -> frozenset[tuple[str, int]]:
        return self._hosts


@asynccontextmanager
async def allowing(engine: Engine, *ports: int) -> AsyncIterator[int]:
    """A proxy letting `localhost` through on each port."""
    hosts = _Fixed(engine, {("localhost", port) for port in ports})
    async with serving_runtime_proxy(
        create_session_factory(engine), "127.0.0.1", 0, allowed=hosts
    ) as port:
        yield port


SEARCH = SourceTool(
    name="search",
    title=None,
    description="Search the notes.",
    input_schema={},
    annotations={"readOnlyHint": True},
)


def connect_plugin(
    engine: Engine,
    url: str,
    *,
    third_party_on: bool = True,
    transport: str = "streamable_http",
) -> None:
    """A connected custom plugin at `url`, with the notes server's read-only search.

    `transport` `sse` records it as one connected over SSE before this release.
    """
    with create_session_factory(engine)() as session:
        plugin = store_custom_plugin(session, "notes", "Notes", url, None, [SEARCH])
        if transport != "streamable_http":
            plugin.entry = {**plugin.entry, "transport": transport}
        set_third_party_on(session, third_party_on)
        session.commit()


async def through(proxy: int, request: bytes) -> tuple[bytes, bytes]:
    """The proxy's answer to `request`, then what came back through it for `ping`."""
    reader, writer = await asyncio.open_connection("127.0.0.1", proxy)
    writer.write(request)
    await writer.drain()
    head = await reader.readuntil(b"\r\n\r\n")
    echoed = b""
    if head.startswith(b"HTTP/1.1 200"):
        writer.write(b"ping")
        await writer.drain()
        echoed = await reader.read(100)
    writer.close()
    return head, echoed


def _connect(port: int) -> bytes:
    return f"CONNECT localhost:{port} HTTP/1.1\r\n\r\n".encode()


async def test_opencodes_proxy_refuses_every_host_a_ready_plugins_too(
    engine: Engine, proxy: int, echo: Echo
) -> None:
    """opencode reaches a plugin only through the gateway, which holds its sign-in."""
    connect_plugin(engine, f"https://localhost:{echo.port}/mcp")

    head, _ = await through(proxy, _connect(echo.port))

    assert head.startswith(b"HTTP/1.1 403")
    assert echo.connections == 0


async def test_an_allowed_host_is_tunnelled_to(engine: Engine, echo: Echo) -> None:
    """The runtime's TLS goes through untouched: SurfSense sees the host, never the content."""
    async with allowing(engine, echo.port) as proxy:
        head, echoed = await through(proxy, _connect(echo.port))

    assert head.startswith(b"HTTP/1.1 200")
    assert echoed == b"ping"


async def test_a_plain_http_request_is_refused(engine: Engine, echo: Echo) -> None:
    """Only tunnels pass, even to an allowed host."""
    async with allowing(engine, echo.port) as proxy:
        head, _ = await through(
            proxy,
            f"GET http://localhost:{echo.port}/ HTTP/1.1\r\nHost: x\r\n\r\n".encode(),
        )

    assert head.startswith(b"HTTP/1.1 403")
    assert echo.connections == 0


def test_a_call_recorded_leaves_the_hosts_held(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A host's last call is written while tunnels open; it changes no consent."""
    monkeypatch.setattr(allowed_hosts, "TTL_SECONDS", 3600.0)
    with create_session_factory(engine)() as session:
        set_enabled(session, "host:api.example", True)
        session.commit()
    hosts = _Fixed(engine, {("api.example", 443)})
    read = hosts.read()

    hosts.record_call("host:api.example")

    assert hosts.current() == read == {("api.example", 443)}
    with create_session_factory(engine)() as session:
        recorded = session.get_one(EgressDestination, "host:api.example")
        assert recorded.last_call_at is not None


@contextmanager
def nothing_listening() -> Iterator[int]:
    """A loopback port bound and not listening, so a connection to it is refused."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    try:
        yield sock.getsockname()[1]
    finally:
        sock.close()


async def test_a_host_that_cannot_be_reached_is_answered(engine: Engine) -> None:
    """The runtime is told at once, rather than left with a socket closed on it."""
    with nothing_listening() as port:
        async with allowing(engine, port) as proxy:
            head, _ = await through(proxy, _connect(port))

    assert head.startswith(b"HTTP/1.1 502")


async def test_a_connect_that_fails_in_any_way_is_answered(
    engine: Engine, echo: Echo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not only a network error: a dropped socket reads as a blip, and is retried blindly."""

    async def unexpected(_host: str, _port: int) -> None:
        raise RuntimeError("the loop refused the call")

    monkeypatch.setattr(server, "_connect", unexpected)

    async with allowing(engine, echo.port) as proxy:
        head, _ = await through(proxy, _connect(echo.port))

    assert head.startswith(b"HTTP/1.1 502")


async def test_a_check_that_fails_is_answered(
    engine: Engine, echo: Echo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A database held by another writer past its wait fails the connection with an answer."""

    def locked(_self: AllowedHosts) -> frozenset[tuple[str, int]]:
        raise OperationalError("BEGIN IMMEDIATE", {}, Exception("database is locked"))

    monkeypatch.setattr(AllowedHosts, "read", locked)

    async with allowing(engine, echo.port) as proxy:
        head, _ = await through(proxy, _connect(echo.port))

    assert head.startswith(b"HTTP/1.1 502")
    assert echo.connections == 0


async def test_a_runtime_gone_before_its_answer_closes_the_hosts_connection(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tunnel never opens, so nothing else would close the host's side of it."""
    drain = asyncio.StreamWriter.drain
    # Held, as the runtime's reader holds the error a reset leaves on it: the host's
    # connection is not then closed by being collected, only by the proxy.
    raised: list[ConnectionResetError] = []
    loop = asyncio.get_running_loop()
    # A bare socket, so a connection left open fails the test rather than hanging it.
    with socket.create_server(("127.0.0.1", 0)) as host:
        host.setblocking(False)
        port = host.getsockname()[1]
        async with allowing(engine, port) as proxy:

            async def reset(writer: asyncio.StreamWriter) -> None:
                # The proxy's 200 fails, as it does once the runtime reset the connection.
                if writer.get_extra_info("sockname")[1] == proxy:
                    raised.append(ConnectionResetError())
                    raise raised[-1]
                await drain(writer)

            monkeypatch.setattr(asyncio.StreamWriter, "drain", reset)
            reader, writer = await asyncio.open_connection("127.0.0.1", proxy)
            writer.write(_connect(port))
            await writer.drain()
            await reader.read()
            writer.close()
            tunnel, _ = await asyncio.wait_for(loop.sock_accept(host), 5)
            with tunnel:
                received = await asyncio.wait_for(loop.sock_recv(tunnel, 100), 5)

    assert received == b""


@pytest.fixture
def remote_notes() -> Iterator[str]:
    """The notes server named `localhost`, which opencode's proxy settings do not exempt."""
    with serving(notes_server().streamable_http_app()) as base:
        yield f"{base.replace('127.0.0.1', 'localhost')}/mcp"


@pytest.fixture
def opencode_env(proxy: int) -> dict[str, str]:
    """opencode as Electron starts it, its proxy SurfSense's; only 127.0.0.1 skips it here."""
    through = f"http://127.0.0.1:{proxy}"
    return {
        "HTTP_PROXY": through,
        "HTTPS_PROXY": through,
        "ALL_PROXY": through,
        "NO_PROXY": "127.0.0.1,::1",
    }


async def test_the_agent_reaches_a_remote_plugin_while_its_proxy_refuses_every_host(
    agent_api: AgentAPI,
    engine: Engine,
    remote_notes: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The gateway is on loopback, so the plugin is called with no connection through the proxy."""
    caplog.set_level(logging.INFO, logger="modules.agent.runtime_proxy.server")
    connect_plugin(engine, remote_notes)
    with create_session_factory(engine)() as session:
        session.get_one(PluginTool, ("notes", "search")).approval = ToolApproval.ALWAYS
        session.commit()
    agent_api.model.replies = [
        ("call", '{"name": "notes_search", "arguments": {"query": "ship"}}'),
        ("text", "Done."),
    ]
    thread = await open_thread(agent_api)

    frames = await send(agent_api, thread["id"], "Search my notes")

    assert of_type(frames, "agent-plugins-unavailable") == []
    step = of_type(frames, "agent-step")[-1]
    assert (step["tool"], step["status"]) == ("notes_search", "completed")
    # Nothing tunnelled, and nothing even asked for: opencode opened no connection off loopback.
    assert "checked in" not in caplog.text
    assert "refused" not in caplog.text


async def test_the_api_runs_the_proxy_where_electron_points_opencode(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Electron picks the port and gives it to both; the API listens there while it runs."""
    port = free_port()
    monkeypatch.setattr(get_agent_settings(), "opencode_proxy_port", port)

    async with lifespan(create_app()):
        head, _ = await through(port, b"CONNECT example.com:443 HTTP/1.1\r\n\r\n")

    assert head.startswith(b"HTTP/1.1 403")


def test_an_allowed_host_is_tunnelled_to_under_uvloop(engine: Engine) -> None:
    """The real app runs on uvloop on macOS and Linux; the tests' loop is asyncio's."""
    # uvloop has no Windows build, and the app runs on asyncio's own loop there.
    uvloop = pytest.importorskip("uvloop")

    async def tunnelled() -> tuple[bytes, bytes]:
        async def answer(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            writer.write(await reader.read(100))
            await writer.drain()
            writer.close()

        echoing = await asyncio.start_server(answer, "127.0.0.1", 0)
        port = echoing.sockets[0].getsockname()[1]
        async with echoing, allowing(engine, port) as proxy:
            return await through(proxy, _connect(port))

    head, echoed = uvloop.run(tunnelled())

    assert head.startswith(b"HTTP/1.1 200")
    assert echoed == b"ping"
