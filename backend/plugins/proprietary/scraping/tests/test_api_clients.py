"""The kept vendor API clients: one per base URL and event loop, closed at shutdown."""

import asyncio
import threading
from collections.abc import AsyncIterator, Iterator

import httpx2
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from host.tests.serving import serving
from proprietary.scraping import api_clients, lifecycle
from proprietary.scraping.api_clients import api_client, close_clients


@pytest.fixture(autouse=True)
async def closed() -> AsyncIterator[None]:
    yield
    await close_clients()


@pytest.fixture
def other_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """A loop running in a thread of its own, as the browser loop does."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join()
    loop.close()


async def made() -> httpx2.AsyncClient:
    return api_client("https://api.capsolver.com")


async def test_one_client_per_base_url() -> None:
    capsolver = api_client("https://api.capsolver.com")

    assert api_client("https://api.capsolver.com/") is capsolver
    assert api_client("https://2captcha.com") is not capsolver
    assert capsolver.base_url == "https://api.capsolver.com"


async def test_requests_keep_their_connection() -> None:
    """A new client paid a TLS handshake on every request; a kept one reuses it."""
    ports: list[int] = []

    async def ping(request: Request) -> PlainTextResponse:
        assert request.client is not None
        ports.append(request.client.port)
        return PlainTextResponse("pong")

    with serving(Starlette(routes=[Route("/ping", ping)])) as url:
        for _ in range(3):
            assert (await api_client(url).get("/ping")).text == "pong"

    assert len(ports) == 3
    assert len(set(ports)) == 1


async def test_each_loop_has_its_own_client(
    other_loop: asyncio.AbstractEventLoop,
) -> None:
    """A client belongs to the loop that made it; captcha solves run on the browser loop."""
    elsewhere = await asyncio.wrap_future(
        asyncio.run_coroutine_threadsafe(made(), other_loop)
    )

    assert api_client("https://api.capsolver.com") is not elsewhere


async def test_a_gone_loop_s_clients_are_dropped() -> None:
    gone = await asyncio.to_thread(asyncio.run, made())
    here = api_client("https://api.capsolver.com")

    assert here is not gone
    assert all(loop is asyncio.get_running_loop() for loop, _ in api_clients._clients)


async def test_shutdown_closes_every_client_on_its_own_loop(
    other_loop: asyncio.AbstractEventLoop,
) -> None:
    here = api_client("https://api.capsolver.com")
    elsewhere = await asyncio.wrap_future(
        asyncio.run_coroutine_threadsafe(made(), other_loop)
    )

    # What the host's shutdown runs, through the lifecycle.
    assert close_clients in lifecycle._closers
    await close_clients()

    assert here.is_closed
    assert elsewhere.is_closed
    assert api_client("https://api.capsolver.com") is not here
