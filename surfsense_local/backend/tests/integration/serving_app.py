"""An app served on a real port for one test, and gone when it ends.

A server left running keeps its lifespan's schedules, which share process-wide state with
every later test: one took a held-back job pack code from the schedule under test.
"""

import asyncio
import socket
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from starlette.types import ASGIApp

# Uvicorn waits for open connections with no limit unless told one.
OPEN_CONNECTIONS_SECONDS = 2
# That wait, then the lifespan's own shutdown, whose schedules take up to 2 s to stop.
STOP_SECONDS = 15


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@asynccontextmanager
async def serving_app(app: ASGIApp, port: int | None = None) -> AsyncIterator[str]:
    """Yields the app's address: on `port` when its settings already name one."""
    port = port or _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            timeout_graceful_shutdown=OPEN_CONNECTIONS_SECONDS,
        )
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
        thread.join(timeout=STOP_SECONDS)
        if thread.is_alive():
            raise RuntimeError(f"the app on port {port} did not stop")
