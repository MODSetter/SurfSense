import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from shared.config import get_llm_settings


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
