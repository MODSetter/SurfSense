import json
import secrets
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from modules.agent.opencode_config import AgentSetup, write_opencode_config
from shared.config import get_llm_settings
from tests.integration.agent.opencode_harness import (
    MODEL,
    RunningOpencode,
    ScriptedHandler,
    ScriptedModel,
    free_port,
    needs_staged_opencode,
    start_opencode,
    wait_until_healthy,
)


@dataclass
class Received:
    """One request the model server was sent, as it arrived."""

    path: str
    headers: dict[str, str]
    body: dict


@dataclass
class StubModel:
    """An OpenAI-compatible model server: records each request, answers as told."""

    url: str = ""
    requests: list[Received] = field(default_factory=list)
    status: int = 200
    # The SSE `data:` payloads a streamed reply carries, `[DONE]` included or not.
    frames: list[str] = field(
        default_factory=lambda: [
            json.dumps({"choices": [{"delta": {"content": "Hello"}}]}),
            json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
            "[DONE]",
        ]
    )
    # Sent instead of the frames when `status` is an error.
    error_body: str = ""


class _Handler(BaseHTTPRequestHandler):
    """Answers `POST …/chat/completions` from the stub the server carries."""

    def do_POST(self) -> None:
        stub: StubModel = self.server.stub  # type: ignore[attr-defined]
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        stub.requests.append(Received(self.path, dict(self.headers), json.loads(raw)))
        if stub.status >= 400:
            body = stub.error_body.encode()
            self.send_response(stub.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for frame in stub.frames:
            self.wfile.write(f"data: {frame}\n\n".encode())
            self.wfile.flush()

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def model_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[StubModel]:
    """A real model server on a real port, which llama-server's address points at."""
    stub = StubModel()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.stub = stub  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    stub.url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_llm_settings(), "llamacpp_base_url", stub.url)

    yield stub

    server.shutdown()
    server.server_close()


@pytest.fixture
def scripted_model() -> Iterator[ScriptedModel]:
    """A model on a real port that opencode's provider is pointed at."""
    model = ScriptedModel()
    server = ThreadingHTTPServer(("127.0.0.1", 0), ScriptedHandler)
    server.model = model  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    model.url = f"http://127.0.0.1:{server.server_port}"
    yield model
    model.release.set()
    server.shutdown()
    server.server_close()


@pytest.fixture
def opencode(
    tmp_path: Path, scripted_model: ScriptedModel
) -> Iterator[RunningOpencode]:
    """The staged opencode on SurfSense's own configuration, its model scripted."""
    needs_staged_opencode()
    agent_dir = tmp_path / "agent"
    setup = AgentSetup(
        model=MODEL,
        window=32768,
        endpoint_url=f"{scripted_model.url}/v1",
        launch_key="launch-key",
    )
    write_opencode_config(agent_dir / "opencode.json", setup)
    running = start_opencode(agent_dir, free_port(), secrets.token_urlsafe(16))
    try:
        wait_until_healthy(running)
        yield running
    finally:
        running.stop()
