import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from shared.config import get_llm_settings

INSTALLED = ["qwen3:1.7b", "qwen3:4b"]
PULL_STEPS = [
    {"status": "pulling manifest"},
    {"status": "downloading", "completed": 40, "total": 100},
    {"status": "downloading", "completed": 100, "total": 100},
    {"status": "success"},
]


class StubOllama(BaseHTTPRequestHandler):
    """Enough of Ollama's native API for the router to talk to."""

    def do_GET(self) -> None:
        if self.path == "/":
            self._send(b"Ollama is running")
        elif self.path == "/api/tags":
            self._json({"models": [{"name": name} for name in INSTALLED]})
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        # Drain the request body so the client's connection can be reused.
        self.rfile.read(int(self.headers["Content-Length"]))
        if self.path == "/api/show":
            self._json({"capabilities": ["completion", "tools"]})
        elif self.path == "/api/pull":
            lines = "".join(json.dumps(step) + "\n" for step in PULL_STEPS)
            self._send(lines.encode())
        else:
            self.send_error(404)

    def _json(self, payload: dict) -> None:
        self._send(json.dumps(payload).encode())

    def _send(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def ollama_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A real Ollama stand-in on a real port, pointed to by settings."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_llm_settings(), "ollama_base_url", url)

    yield url

    server.shutdown()
    server.server_close()


# One text model, one image model: the provider keeps the first, drops the second.
OPENROUTER_MODELS = [
    {
        "id": "anthropic/claude-3.5-sonnet",
        "architecture": {"output_modalities": ["text"]},
    },
    {"id": "black-forest-labs/flux", "architecture": {"output_modalities": ["image"]}},
]
CHAT_DELTAS = ["Hel", "lo"]


class StubOpenRouter(BaseHTTPRequestHandler):
    """Enough of OpenRouter's OpenAI-compatible API for the provider to talk to."""

    def do_GET(self) -> None:
        if self.path == "/key":
            self._json({"data": {"label": "test-key"}})
        elif self.path == "/models":
            self._json({"data": OPENROUTER_MODELS})
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers["Content-Length"]))
        if self.path != "/chat/completions":
            self.send_error(404)
            return
        frames = [
            f"data: {json.dumps({'choices': [{'delta': {'content': text}}]})}\n\n"
            for text in CHAT_DELTAS
        ]
        frames.append("data: [DONE]\n\n")
        self._send("".join(frames).encode())

    def _json(self, payload: dict) -> None:
        self._send(json.dumps(payload).encode())

    def _send(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def openrouter_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A real OpenRouter stand-in on a real port, pointed to by settings."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubOpenRouter)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_llm_settings(), "openrouter_base_url", url)

    yield url

    server.shutdown()
    server.server_close()
