"""The freshness push end to end: an /internal/events POST reaches a subscriber.

Run against a real uvicorn server over TCP, not the in-process ASGI transport:
that transport awaits the app to completion before returning a response, so it
can never read an endless SSE stream incrementally (it would hang). A real socket
is also closer to what the renderer's EventSource actually does.
"""

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
    """Serve a migrated app on a free port; data_dir points it at this test's DB."""
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


async def _line_starting(lines: AsyncIterator[str], prefix: str) -> str:
    async for line in lines:
        if line.startswith(prefix):
            return line
    raise AssertionError(f"stream ended before a line starting {prefix!r}")


async def test_an_internal_event_reaches_a_subscriber(base_url: str) -> None:
    """A worker notice arrives on the workspace's stream as a named SSE frame."""
    async with AsyncClient(base_url=base_url, timeout=5) as client:
        workspace_id = (await client.post("/workspaces", json={"name": "w"})).json()[
            "id"
        ]

        async with client.stream(
            "GET", f"/workspaces/{workspace_id}/events"
        ) as reply:
            assert reply.status_code == 200
            assert reply.headers["content-type"].startswith("text/event-stream")
            lines = reply.aiter_lines()

            # Wait until subscribed, so the POST below cannot race ahead of us.
            await _line_starting(lines, ": connected")

            posted = await client.post(
                "/internal/events",
                json={
                    "workspace_id": workspace_id,
                    "kind": "documents",
                    "ids": [7],
                    "status": "ready",
                },
            )
            assert posted.status_code == 202

            assert await _line_starting(lines, "event:") == "event: documents"
            data = await _line_starting(lines, "data:")
            assert json.loads(data.removeprefix("data: ")) == {
                "ids": [7],
                "status": "ready",
            }


async def test_an_unknown_workspace_stream_is_a_404(base_url: str) -> None:
    """The stream validates the workspace like every other workspace-scoped route."""
    async with AsyncClient(base_url=base_url, timeout=5) as client:
        assert (await client.get("/workspaces/9999/events")).status_code == 404
