"""The proxy Claude Code's traffic goes through: Anthropic's two hosts, only while allowed."""

import asyncio
import logging
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import Engine

from modules.egress.service import set_enabled
from modules.llm.subscriptions.claude import proxy as claude_proxy
from modules.llm.subscriptions.claude.proxy_hosts import ClaudeHosts
from shared.db import create_session_factory
from tests.integration.agent.test_runtime_proxy import Echo, connect_plugin, through

pytestmark = pytest.mark.integration


def _allow(engine: Engine, *hosts: str) -> None:
    with create_session_factory(engine)() as session:
        for host in hosts:
            set_enabled(session, f"host:{host}", True)
        session.commit()


@pytest_asyncio.fixture(loop_scope="function")
async def proxy(engine: Engine) -> AsyncIterator[int]:
    """The Claude proxy as the API serves it, on a free loopback port."""
    async with claude_proxy.serving_claude_proxy(
        create_session_factory(engine), "127.0.0.1"
    ) as port:
        yield port


@pytest_asyncio.fixture(loop_scope="function")
async def echo() -> AsyncIterator[Echo]:
    """A server that sends back what it is sent, standing in for an allowed host."""
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


@pytest.mark.parametrize("host", ["api.anthropic.com", "platform.claude.com"])
async def test_a_claude_host_is_refused_until_allowed(
    engine: Engine, proxy: int, host: str
) -> None:
    """Refused before any connection is tried, so nothing leaves the machine."""
    head, _ = await through(proxy, f"CONNECT {host}:443 HTTP/1.1\r\n\r\n".encode())

    assert head.startswith(b"HTTP/1.1 403")


async def test_no_other_host_is_ever_let_through(engine: Engine, proxy: int) -> None:
    """Even one the user allowed for something else: Claude Code reaches Anthropic only."""
    _allow(engine, "huggingface.co")

    head, _ = await through(proxy, b"CONNECT huggingface.co:443 HTTP/1.1\r\n\r\n")

    assert head.startswith(b"HTTP/1.1 403")


def test_each_host_is_let_through_only_while_it_is_allowed(engine: Engine) -> None:
    """Turning one off in Settings > Network closes that host alone."""
    hosts = ClaudeHosts(create_session_factory(engine))
    _allow(engine, "api.anthropic.com")

    assert hosts.read() == {("api.anthropic.com", 443)}

    _allow(engine, "platform.claude.com")

    assert hosts.read() == {("api.anthropic.com", 443), ("platform.claude.com", 443)}


async def test_an_allowed_host_is_tunnelled_to(engine: Engine, echo: Echo) -> None:
    """Claude Code's TLS goes through untouched: SurfSense sees the host, never the content."""
    async with claude_proxy.serving_claude_proxy(
        create_session_factory(engine), "127.0.0.1", hosts=(("localhost", echo.port),)
    ) as port:
        head, echoed = await through(
            port, f"CONNECT localhost:{echo.port} HTTP/1.1\r\n\r\n".encode()
        )

    assert head.startswith(b"HTTP/1.1 200")
    assert echoed == b"ping"


async def test_runs_know_the_proxys_address_only_while_it_serves(
    engine: Engine,
) -> None:
    """Every Claude Code run reads it; outside the API there is none."""
    assert claude_proxy.claude_proxy_url() is None

    async with claude_proxy.serving_claude_proxy(
        create_session_factory(engine), "127.0.0.1"
    ) as port:
        assert claude_proxy.claude_proxy_url() == f"http://127.0.0.1:{port}"

    assert claude_proxy.claude_proxy_url() is None


async def test_a_refused_host_is_logged_as_claude_codes(
    engine: Engine, proxy: int, caplog: pytest.LogCaptureFixture
) -> None:
    """A host a future Claude Code tries on its own shows in the log at once."""
    caplog.set_level(logging.INFO)

    await through(proxy, b"CONNECT console.anthropic.com:443 HTTP/1.1\r\n\r\n")

    refused = [
        r.getMessage() for r in caplog.records if r.getMessage().startswith("refused")
    ]
    assert refused == ["refused Claude Code's CONNECT console.anthropic.com:443"]


async def test_a_plugins_host_is_refused_in_chat_and_agent_runs_alike(
    engine: Engine, proxy: int, echo: Echo
) -> None:
    """Claude Code reaches a plugin only through the gateway, which holds its sign-in."""
    connect_plugin(engine, f"https://localhost:{echo.port}/mcp")

    head, _ = await through(
        proxy, f"CONNECT localhost:{echo.port} HTTP/1.1\r\n\r\n".encode()
    )

    assert head.startswith(b"HTTP/1.1 403")
    assert echo.connections == 0
