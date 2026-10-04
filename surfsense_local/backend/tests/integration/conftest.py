import asyncio
import socket
import threading
from collections.abc import AsyncIterator

import pytest
import uvicorn
from sqlalchemy import Engine

from api.main import create_app


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
async def base_url(data_dir: object, engine: Engine) -> AsyncIterator[str]:
    """Serve a migrated app on a free port; data_dir points it at this test's DB,
    which `engine` has already built with the embedder fixed, as onboarding would."""
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
