"""The host, or a stand-in for a service it calls, served on loopback for a test."""

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import uvicorn
from starlette.types import ASGIApp


@contextmanager
def serving(app: ASGIApp) -> Iterator[str]:
    """Serve `app` on a free loopback port and yield its base URL."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    # A client holding its stream open must not keep the server up.
    config = uvicorn.Config(
        app, log_level="warning", lifespan="on", timeout_graceful_shutdown=1
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
    thread.start()
    while not server.started:
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join()
