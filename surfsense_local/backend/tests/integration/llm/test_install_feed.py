"""The install feed end to end, over a real socket: the in-process transport
waits for a response to finish, and this one never does."""

import asyncio
import json
import socket
import threading
from collections.abc import AsyncIterator

import pytest
import uvicorn
from httpx import AsyncClient

from api.main import create_app

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
async def base_url(data_dir: object) -> AsyncIterator[str]:
    """A migrated app on a free port; data_dir points it at this test's DB."""
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.05)
        else:
            raise RuntimeError("server did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


async def test_the_feed_opens_with_every_job(base_url: str) -> None:
    """Its first frame is the whole list, so a screen that connects late or
    reconnects needs nothing it missed."""
    async with (
        AsyncClient(base_url=base_url, timeout=5) as client,
        client.stream("GET", "/llm/installs/events") as reply,
    ):
        assert reply.headers["content-type"].startswith("application/x-ndjson")
        first = await anext(reply.aiter_lines())

    assert json.loads(first) == {"jobs": []}
