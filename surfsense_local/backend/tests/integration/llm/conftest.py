import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from shared.config import get_llm_settings

INSTALLED = ["qwen3:1.7b", "qwen3:4b"]
DELETED: list[str] = []
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
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/show":
            self._json(
                {
                    "capabilities": ["completion", "tools"],
                    "details": {"quantization_level": "Q4_K_M"},
                }
            )
        elif self.path == "/api/pull":
            if body["model"] not in INSTALLED:
                INSTALLED.append(body["model"])
            lines = "".join(json.dumps(step) + "\n" for step in PULL_STEPS)
            self._send(lines.encode())
        else:
            self.send_error(404)

    def do_DELETE(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path != "/api/delete" or body["model"] not in INSTALLED:
            self.send_error(404)
            return
        INSTALLED.remove(body["model"])
        DELETED.append(body["model"])
        self._send(b"")

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
    INSTALLED[:] = ["qwen3:1.7b", "qwen3:4b"]
    DELETED.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_llm_settings(), "ollama_base_url", url)

    yield url

    server.shutdown()
    server.server_close()


REMOTE_MODELS = [
    {
        "id": "anthropic/claude-3.5-sonnet",
        "architecture": {"output_modalities": ["text"]},
    },
    {"id": "black-forest-labs/flux", "architecture": {"output_modalities": ["image"]}},
]
CHAT_DELTAS = ["Hel", "lo"]
REMOTE_REQUESTS: list[tuple[str, str]] = []


class StubOpenAICompatible(BaseHTTPRequestHandler):
    """Chat, model discovery, and image APIs behind one connection."""

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/models":
            image_only = parse_qs(parsed.query).get("output_modalities") == ["image"]
            models = REMOTE_MODELS[1:] if image_only else REMOTE_MODELS[:1]
            self._json({"object": "list", "data": models})
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"]))
        REMOTE_REQUESTS.append((self.path, body.decode()))
        if self.path == "/chat/completions":
            frames = [
                f"data: {json.dumps({'choices': [{'delta': {'content': text}}]})}\n\n"
                for text in CHAT_DELTAS
            ]
            frames.append("data: [DONE]\n\n")
            self._send("".join(frames).encode())
        elif self.path == "/images/generations":
            encoded = "iVBORw0KGgpmYWtl"
            self._json({"data": [{"b64_json": encoded, "media_type": "image/png"}]})
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
def openai_server() -> Iterator[str]:
    """A real OpenAI-compatible endpoint on a real port."""
    REMOTE_REQUESTS.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubOpenAICompatible)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"

    yield url

    server.shutdown()
    server.server_close()
