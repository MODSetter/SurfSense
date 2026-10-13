"""The proxy opencode reaches the network through: a tunnel to a ready plugin's host, and nothing else."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import Engine

from api.main import create_app, lifespan
from modules.agent.plugin_proxy.server import serving_plugin_proxy
from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.custom_plugin import store_custom_plugin
from modules.plugins.installed.models import PluginTool, ToolApproval
from modules.plugins.installed.plugin_switch import set_plugin_enabled
from modules.plugins.installed.third_party import set_third_party_on
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


def connect_plugin(engine: Engine, url: str, *, third_party_on: bool = True) -> None:
    """A connected custom plugin at `url`, with the notes server's read-only search."""
    tool = SourceTool(
        name="search",
        title=None,
        description="Search the notes.",
        input_schema={},
        annotations={"readOnlyHint": True},
    )
    with create_session_factory(engine)() as session:
        store_custom_plugin(session, "notes", "Notes", url, None, [tool])
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


async def test_a_plugin_not_ready_is_refused_from_its_next_connection(
    engine: Engine, proxy: int, echo: Echo
) -> None:
    """Readiness is read on each connection, so switching a plugin off cuts it at once."""
    connect_plugin(engine, f"https://localhost:{echo.port}/mcp")
    with create_session_factory(engine)() as session:
        set_plugin_enabled(session, "notes", False)
        session.commit()

    head, _ = await through(
        proxy, f"CONNECT localhost:{echo.port} HTTP/1.1\r\n\r\n".encode()
    )

    assert head.startswith(b"HTTP/1.1 403")


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
    agent_api: AgentAPI, engine: Engine, https_notes: tuple[str, Path]
) -> None:
    """opencode's only way out is the proxy, which lets the ready plugin's host through."""
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


async def test_the_api_runs_the_proxy_where_electron_points_opencode(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Electron picks the port and gives it to both; the API listens there while it runs."""
    port = free_port()
    monkeypatch.setattr(get_agent_settings(), "plugin_proxy_port", port)

    async with lifespan(create_app()):
        head, _ = await through(port, b"CONNECT example.com:443 HTTP/1.1\r\n\r\n")

    assert head.startswith(b"HTTP/1.1 403")
