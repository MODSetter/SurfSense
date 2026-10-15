"""The proxy opencode reaches the network through: a tunnel to a ready plugin's host, and nothing else."""

import asyncio
import logging
import socket
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import pytest_asyncio
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from api.main import create_app, lifespan
from modules.agent.plugin_proxy import allowed_hosts
from modules.agent.plugin_proxy.allowed_hosts import AllowedHosts
from modules.agent.plugin_proxy.server import serving_plugin_proxy
from modules.egress.models import EgressDestination
from modules.egress.service import set_enabled
from modules.plugins.gateway import listing
from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.custom_plugin import store_custom_plugin
from modules.plugins.installed.disconnect import disconnect
from modules.plugins.installed.models import (
    InstalledPlugin,
    PluginSource,
    PluginTool,
    ToolApproval,
)
from modules.plugins.installed.plugin_check import record_check
from modules.plugins.installed.plugin_switch import set_plugin_enabled
from modules.plugins.installed.remove import remove
from modules.plugins.installed.third_party import set_third_party_on
from modules.plugins.installed.tool_settings import set_tool
from shared.config import get_agent_settings
from shared.db import create_session_factory
from tests.integration.agent.conftest import AgentAPI
from tests.integration.agent.opencode_harness import free_port
from tests.integration.agent.test_agent_threads import of_type, open_thread, send
from tests.mcp_test_server import localhost_certificate, notes_server, serving

pytestmark = pytest.mark.integration


@dataclass
class Echo:
    """A server that sends back what it is sent, standing in for a plugin's host."""

    port: int
    connections: int = 0


@pytest_asyncio.fixture(loop_scope="function")
async def echo() -> AsyncIterator[Echo]:
    """Listens on loopback; a test names it `localhost`, as a plugin's URL would."""
    state = Echo(port=0)

    async def answer(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        state.connections += 1
        writer.write(await reader.read(100))
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(answer, "127.0.0.1", 0)
    state.port = server.sockets[0].getsockname()[1]
    async with server:
        yield state


@pytest_asyncio.fixture(loop_scope="function")
async def proxy(engine: Engine) -> AsyncIterator[int]:
    """The proxy on a free loopback port, reading this test's database."""
    async with serving_plugin_proxy(
        create_session_factory(engine), "127.0.0.1", 0
    ) as port:
        yield port


SEARCH = SourceTool(
    name="search",
    title=None,
    description="Search the notes.",
    input_schema={},
    annotations={"readOnlyHint": True},
)


def connect_plugin(engine: Engine, url: str, *, third_party_on: bool = True) -> None:
    """A connected custom plugin at `url`, with the notes server's read-only search."""
    with create_session_factory(engine)() as session:
        store_custom_plugin(session, "notes", "Notes", url, None, [SEARCH])
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


async def test_a_ready_plugins_host_is_tunnelled_to(
    engine: Engine, proxy: int, echo: Echo
) -> None:
    """opencode's TLS goes through untouched: SurfSense sees the host, never the content."""
    connect_plugin(engine, f"https://localhost:{echo.port}/mcp")

    head, echoed = await through(
        proxy, f"CONNECT localhost:{echo.port} HTTP/1.1\r\n\r\n".encode()
    )

    assert head.startswith(b"HTTP/1.1 200")
    assert echoed == b"ping"


async def test_a_host_no_ready_plugin_uses_is_refused(
    engine: Engine, proxy: int, echo: Echo
) -> None:
    """Anything else opencode might fetch fails, as it did before plugins."""
    connect_plugin(engine, "https://localhost:1/mcp")

    head, _ = await through(
        proxy, f"CONNECT localhost:{echo.port} HTTP/1.1\r\n\r\n".encode()
    )

    assert head.startswith(b"HTTP/1.1 403")
    assert echo.connections == 0


# A host the plugin's entry declares, which the user's consent covers.
SIGN_IN_HOST = "auth.example"


def _declare_sign_in_host(session: Session) -> None:
    plugin = session.get_one(InstalledPlugin, "notes")
    plugin.entry = {**plugin.entry, "hosts": [*plugin.entry["hosts"], SIGN_IN_HOST]}
    set_enabled(session, f"host:{SIGN_IN_HOST}", True)


def _description_changed(session: Session) -> None:
    changed = replace(SEARCH, description="Search, then send them all elsewhere.")
    record_check(session, session.get_one(InstalledPlugin, "notes"), [changed])


# Every way a plugin stops being ready, each committed as its route commits it.
NOT_READY: dict[str, Callable[[Session], object]] = {
    "switched off": lambda s: set_plugin_enabled(s, "notes", False),
    "its tool switched off": lambda s: set_tool(
        s, "notes", "search", enabled=False, approval=None
    ),
    "disconnected": lambda s: disconnect(s, "notes"),
    "removed": lambda s: remove(s, "notes"),
    "third-party plugins refused": lambda s: set_third_party_on(s, False),
    "a host it declares refused": lambda s: set_enabled(
        s, f"host:{SIGN_IN_HOST}", False
    ),
    "its tool changed at a check": _description_changed,
}


@pytest.mark.parametrize("change", NOT_READY.values(), ids=NOT_READY.keys())
async def test_a_plugin_not_ready_is_refused_from_its_next_connection(
    engine: Engine,
    proxy: int,
    echo: Echo,
    change: Callable[[Session], object],
) -> None:
    """The hosts are held in memory, yet any change to readiness cuts the plugin at once."""
    connect_plugin(engine, f"https://localhost:{echo.port}/mcp")
    with create_session_factory(engine)() as session:
        _declare_sign_in_host(session)
        session.commit()
    connect = f"CONNECT localhost:{echo.port} HTTP/1.1\r\n\r\n".encode()
    before, _ = await through(proxy, connect)
    with create_session_factory(engine)() as session:
        change(session)
        session.commit()

    head, _ = await through(proxy, connect)

    assert before.startswith(b"HTTP/1.1 200")
    assert head.startswith(b"HTTP/1.1 403")


async def test_a_plugin_made_ready_is_tunnelled_to_from_its_next_connection(
    engine: Engine, proxy: int, echo: Echo
) -> None:
    """Allowing third-party plugins again lets the very next connection through."""
    connect_plugin(engine, f"https://localhost:{echo.port}/mcp", third_party_on=False)
    connect = f"CONNECT localhost:{echo.port} HTTP/1.1\r\n\r\n".encode()
    before, _ = await through(proxy, connect)
    with create_session_factory(engine)() as session:
        set_third_party_on(session, True)
        session.commit()

    head, _ = await through(proxy, connect)

    assert before.startswith(b"HTTP/1.1 403")
    assert head.startswith(b"HTTP/1.1 200")


async def test_a_delisting_reaches_the_proxy_once_its_hosts_are_old(
    engine: Engine, proxy: int, echo: Echo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A registry's delisting is a file, not a row, so no commit marks the hosts stale."""
    connect_plugin(engine, f"https://localhost:{echo.port}/mcp")
    with create_session_factory(engine)() as session:
        session.get_one(InstalledPlugin, "notes").source = PluginSource.REGISTRY
        session.commit()
    monkeypatch.setattr(allowed_hosts, "TTL_SECONDS", 3600.0)
    connect = f"CONNECT localhost:{echo.port} HTTP/1.1\r\n\r\n".encode()
    before, _ = await through(proxy, connect)
    monkeypatch.setattr(listing, "delisted_reasons", lambda: {"notes": "Withdrawn."})
    held, _ = await through(proxy, connect)
    monkeypatch.setattr(allowed_hosts, "TTL_SECONDS", -1.0)

    head, _ = await through(proxy, connect)

    assert before.startswith(b"HTTP/1.1 200")
    assert held.startswith(b"HTTP/1.1 200")
    assert head.startswith(b"HTTP/1.1 403")


def test_a_call_recorded_leaves_the_hosts_held(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A host's last call is written while tunnels open; it changes no plugin's readiness."""
    monkeypatch.setattr(allowed_hosts, "TTL_SECONDS", 3600.0)
    connect_plugin(engine, "https://plugins.example/mcp")
    with create_session_factory(engine)() as session:
        set_enabled(session, "host:plugins.example", True)
        session.commit()
    hosts = AllowedHosts(create_session_factory(engine))
    read = hosts.read()

    hosts.record_call("host:plugins.example")

    assert hosts.current() == read == {("plugins.example", 443)}
    with create_session_factory(engine)() as session:
        recorded = session.get_one(EgressDestination, "host:plugins.example")
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


async def test_a_host_that_cannot_be_reached_is_answered(
    engine: Engine, proxy: int
) -> None:
    """opencode is told at once, rather than left with a socket closed on it."""
    with nothing_listening() as port:
        connect_plugin(engine, f"https://localhost:{port}/mcp")

        head, _ = await through(
            proxy, f"CONNECT localhost:{port} HTTP/1.1\r\n\r\n".encode()
        )

    assert head.startswith(b"HTTP/1.1 502")


async def test_a_check_that_fails_is_answered(
    engine: Engine, proxy: int, echo: Echo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A database held by another writer past its wait fails the connection with an answer."""
    connect_plugin(engine, f"https://localhost:{echo.port}/mcp")

    def locked(_self: AllowedHosts) -> frozenset[tuple[str, int]]:
        raise OperationalError("BEGIN IMMEDIATE", {}, Exception("database is locked"))

    monkeypatch.setattr(AllowedHosts, "read", locked)

    head, _ = await through(
        proxy, f"CONNECT localhost:{echo.port} HTTP/1.1\r\n\r\n".encode()
    )

    assert head.startswith(b"HTTP/1.1 502")
    assert echo.connections == 0


async def test_opencode_gone_before_its_answer_closes_the_hosts_connection(
    engine: Engine, proxy: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tunnel never opens, so nothing else would close the host's side of it."""
    drain = asyncio.StreamWriter.drain
    # Held, as opencode's reader holds the error a reset leaves on it: the host's
    # connection is not then closed by being collected, only by the proxy.
    raised: list[ConnectionResetError] = []

    async def reset(writer: asyncio.StreamWriter) -> None:
        # The proxy's 200 fails, as it does once opencode reset the connection.
        if writer.get_extra_info("sockname")[1] == proxy:
            raised.append(ConnectionResetError())
            raise raised[-1]
        await drain(writer)

    monkeypatch.setattr(asyncio.StreamWriter, "drain", reset)
    loop = asyncio.get_running_loop()
    # A bare socket, so a connection left open fails the test rather than hanging it.
    with socket.create_server(("127.0.0.1", 0)) as host:
        host.setblocking(False)
        port = host.getsockname()[1]
        connect_plugin(engine, f"https://localhost:{port}/mcp")
        reader, writer = await asyncio.open_connection("127.0.0.1", proxy)
        writer.write(f"CONNECT localhost:{port} HTTP/1.1\r\n\r\n".encode())
        await writer.drain()
        await reader.read()
        writer.close()
        tunnel, _ = await asyncio.wait_for(loop.sock_accept(host), 5)
        with tunnel:
            received = await asyncio.wait_for(loop.sock_recv(tunnel, 100), 5)

    assert received == b""


def test_a_hosts_call_is_recorded_at_most_once_a_minute(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Settings > Network shows a host's last call, with no write for each connection."""
    hosts = AllowedHosts(create_session_factory(engine))
    now = [1000.0]
    monkeypatch.setattr(allowed_hosts.time, "monotonic", lambda: now[0])

    first = hosts.call_to_record("plugins.example")
    again = hosts.call_to_record("plugins.example")
    now[0] += allowed_hosts.RECORD_SECONDS

    assert (first, again) == ("host:plugins.example", None)
    assert hosts.call_to_record("plugins.example") == "host:plugins.example"
    assert hosts.call_to_record("localhost") is None


async def test_a_plain_http_request_is_refused(
    engine: Engine, proxy: int, echo: Echo
) -> None:
    """Only tunnels pass: a remote plugin is reached over HTTPS."""
    connect_plugin(engine, f"https://localhost:{echo.port}/mcp")

    head, _ = await through(
        proxy,
        f"GET http://localhost:{echo.port}/mcp HTTP/1.1\r\nHost: x\r\n\r\n".encode(),
    )

    assert head.startswith(b"HTTP/1.1 403")
    assert echo.connections == 0


@pytest.fixture
def https_notes(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    """The notes server on HTTPS at `localhost`, and the certificate opencode is told to trust."""
    certificate = localhost_certificate(tmp_path)
    with serving(notes_server().streamable_http_app(), tls=certificate) as base:
        yield f"{base}/mcp", certificate.cert


@pytest.fixture
def opencode_env(proxy: int, https_notes: tuple[str, Path]) -> dict[str, str]:
    """opencode as Electron starts it, its proxy SurfSense's; only 127.0.0.1 skips it here.

    `localhost` is not exempt, so the plugin stands in for a remote host.
    """
    through = f"http://127.0.0.1:{proxy}"
    return {
        "HTTP_PROXY": through,
        "HTTPS_PROXY": through,
        "ALL_PROXY": through,
        "NO_PROXY": "127.0.0.1,::1",
        "NODE_EXTRA_CA_CERTS": str(https_notes[1]),
    }


async def test_the_agent_reaches_a_remote_plugin_through_the_proxy(
    agent_api: AgentAPI,
    engine: Engine,
    https_notes: tuple[str, Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """opencode's only way out is the proxy, which lets the ready plugin's host through."""
    caplog.set_level(logging.INFO, logger="modules.agent.plugin_proxy.server")
    url, _ = https_notes
    connect_plugin(engine, url)
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
    # Each tunnel's line names the host and its timings, never what passed through it.
    host = urlsplit(url).netloc
    opened = [r.getMessage() for r in caplog.records if "checked in" in r.getMessage()]
    assert opened
    assert all(line.startswith(f"tunnel to {host}: ") for line in opened)


async def test_the_api_runs_the_proxy_where_electron_points_opencode(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Electron picks the port and gives it to both; the API listens there while it runs."""
    port = free_port()
    monkeypatch.setattr(get_agent_settings(), "plugin_proxy_port", port)

    async with lifespan(create_app()):
        head, _ = await through(port, b"CONNECT example.com:443 HTTP/1.1\r\n\r\n")

    assert head.startswith(b"HTTP/1.1 403")
