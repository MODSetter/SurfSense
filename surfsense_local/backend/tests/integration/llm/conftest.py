import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from modules.llm.catalog.dependencies import get_catalog_service
from shared.config import get_llm_settings

INSTALLED = ["Qwen3-1.7B-Q4_K_M", "Qwen3-4B-Q4_K_M"]
DELETED: list[str] = []


class StubRouter(BaseHTTPRequestHandler):
    """Enough of llama-server's router mode for the adapter to talk to."""

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            self._json({"status": "ok"})
        elif parsed.path == "/props":
            self._json({"role": "router", "model_info": {}})
        elif parsed.path == "/models":
            self._json(
                {
                    "object": "list",
                    "data": [
                        {"id": name, "status": {"value": "unloaded", "args": []}}
                        for name in INSTALLED
                    ],
                }
            )
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path in ("/models/load", "/models/unload"):
            self._json({"success": True})
        elif self.path == "/v1/chat/completions":
            self._send(b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\ndata: [DONE]\n\n')
        else:
            self.send_error(404)
        del body

    def do_DELETE(self) -> None:
        parsed = urlsplit(self.path)
        model = parse_qs(parsed.query).get("model", [""])[0]
        if parsed.path != "/models" or model not in INSTALLED:
            self.send_error(404)
            return
        INSTALLED.remove(model)
        DELETED.append(model)
        self._json({"success": True})

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
def llamacpp_server(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[str]:
    """A real llama-server stand-in on a real port, pointed to by settings.

    Also stages the same models on disk, because that is where the app reads
    its inventory from: the runtime answers questions about models, it is not
    the record of which ones exist.
    """
    INSTALLED[:] = ["Qwen3-1.7B-Q4_K_M", "Qwen3-4B-Q4_K_M"]
    DELETED.clear()
    models = tmp_path_factory.mktemp("models")
    for name in INSTALLED:
        (models / f"{name}.gguf").write_bytes(b"GGUF")
    monkeypatch.setattr(get_llm_settings(), "llamacpp_models_dir", models)
    get_catalog_service.cache_clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubRouter)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_llm_settings(), "llamacpp_base_url", url)

    yield url

    server.shutdown()
    server.server_close()
    get_catalog_service.cache_clear()


REMOTE_MODELS = [
    {
        "id": "anthropic/claude-3.5-sonnet",
        "architecture": {"output_modalities": ["text"]},
    },
    {"id": "black-forest-labs/flux", "architecture": {"output_modalities": ["image"]}},
]
CHAT_DELTAS = ["Hel", "lo"]
# A thinking model on the far end of a connection. It cannot be told to stop,
# because the field that does that is llama.cpp's and a strict endpoint would
# reject it, so the only thing that gets an answer out is a budget it can
# finish thinking inside.
REASONING_DELTAS = ["Okay, "] * 200
REMOTE_THINKS = False
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
            budget = json.loads(body).get("max_tokens")
            deltas = [("reasoning_content", text) for text in REASONING_DELTAS] * (
                1 if REMOTE_THINKS else 0
            ) + [("content", text) for text in CHAT_DELTAS]
            if budget is not None:
                deltas = deltas[:budget]
            frames = [
                f"data: {json.dumps({'choices': [{'delta': {field: text}}]})}\n\n"
                for field, text in deltas
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
