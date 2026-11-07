"""A test's app stops when the test ends, whatever it left open."""

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import StreamingResponse
from starlette.routing import Route

from tests.integration.serving_app import serving_app

pytestmark = pytest.mark.integration


async def test_an_open_stream_does_not_leave_the_app_running() -> None:
    """Its lifespan's schedules would otherwise outlive the test and reach into the next."""
    stopped = threading.Event()

    async def forever(_request: Request) -> StreamingResponse:
        async def chunks() -> AsyncIterator[bytes]:
            while True:
                yield b"x"
                await asyncio.sleep(0.05)

        return StreamingResponse(chunks())

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        yield
        stopped.set()

    app = Starlette(routes=[Route("/", forever)], lifespan=lifespan)
    streaming = asyncio.Event()

    async def read_forever(base: str) -> None:
        async with (
            httpx.AsyncClient(timeout=None) as client,
            client.stream("GET", base) as stream,
        ):
            async for _ in stream.aiter_bytes():
                streaming.set()

    async with serving_app(app) as base:
        reader = asyncio.create_task(read_forever(base))
        await asyncio.wait_for(streaming.wait(), 10)

    # The stream is still open: only now does its reader get to run again.
    reader.cancel()
    with suppress(asyncio.CancelledError, httpx.HTTPError):
        await reader
    assert stopped.is_set()
