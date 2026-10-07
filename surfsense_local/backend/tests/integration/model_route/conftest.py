import contextlib
import json
import threading
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine

from api.main import create_app
from shared.config import get_llm_settings
from shared.db import create_session_factory

LOCAL_MODEL = "Qwen3-4B-Q4_K_M"
OTHER_LOCAL_MODEL = "Qwen3-1.7B-Q4_K_M"
ANSWER = ["Saturn ", "has rings."]


@dataclass
class Runtime:
    """llama-server as the route reaches it: the models it lists, the chat
    requests it received, what it unloaded, and a switch to hold replies open."""

    models: list[str] = field(default_factory=lambda: [LOCAL_MODEL, OTHER_LOCAL_MODEL])
    requests: list[dict] = field(default_factory=list)
    unloaded: list[str] = field(default_factory=list)
    stall: threading.Event | None = None
    status: int | None = None
    slots: int = 1


class _RuntimeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        runtime: Runtime = self.server.runtime  # type: ignore[attr-defined]
        if self.path.startswith("/props"):
            self._json({"total_slots": runtime.slots})
        elif self.path.startswith("/models"):
            self._json(
                {
                    "data": [
                        {"id": name, "status": {"value": "loaded"}}
                        for name in runtime.models
                    ]
                }
            )
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        runtime: Runtime = self.server.runtime  # type: ignore[attr-defined]
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        if self.path == "/models/unload":
            runtime.unloaded.append(body.get("model"))
            self._json({"success": True})
            return
        runtime.requests.append(body)
        if runtime.status is not None:
            payload = json.dumps({"error": {"message": "slow down"}}).encode()
            self.send_response(runtime.status)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for piece in ANSWER:
            chunk = json.dumps({"choices": [{"delta": {"content": piece}}]})
            self.wfile.write(f"data: {chunk}\n\n".encode())
            self.wfile.flush()
        if runtime.stall is not None:
            runtime.stall.wait(timeout=10)
        with contextlib.suppress(OSError):
            self.wfile.write(b"data: [DONE]\n\n")

    def _json(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[Runtime]:
    """The local runtime on a real port, which the app's llama-server address points at."""
    stub = Runtime()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RuntimeHandler)
    server.runtime = stub  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(
        get_llm_settings(),
        "llamacpp_base_url",
        f"http://127.0.0.1:{server.server_port}",
    )
    yield stub
    if stub.stall is not None:
        stub.stall.set()
    server.shutdown()
    server.server_close()


@dataclass
class App:
    """The app driven in-process, so a test can hold admission on its loop."""

    app: FastAPI
    client: AsyncClient


@pytest.fixture
async def api(engine: Engine) -> AsyncIterator[App]:
    """The app on this test's database, driven in-process on the test's loop."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield App(app, client)


class _RemoteHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_error(404)

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for piece in ANSWER:
            chunk = json.dumps({"choices": [{"delta": {"content": piece}}]})
            self.wfile.write(f"data: {chunk}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def remote_connection(engine: Engine) -> Iterator[int]:
    """A remote connection on a real port; loopback is not egress. Yields its id."""
    from modules.llm.models import ProviderConnection

    server = ThreadingHTTPServer(("127.0.0.1", 0), _RemoteHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with create_session_factory(engine)() as session:
        connection = ProviderConnection(
            label="Remote",
            provider="openai_compatible",
            base_url=f"http://127.0.0.1:{server.server_port}",
        )
        session.add(connection)
        session.commit()
        connection_id = connection.id
    yield connection_id
    server.shutdown()
    server.server_close()
