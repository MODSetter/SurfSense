import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from shared.config import get_llm_settings

# The reply the stub streams back, split so the route emits more than one delta.
REPLY_DELTAS = ["Revenue ", "climbed after the launch [1]."]

# Each chat request the stub received, so a test can assert what the route sent.
_REQUESTS: list[dict] = []

# The context window /props reports, or None to omit it (an older build /
# a model report a test does not care about). Set per test before the fixture
# starts the server.
_PROPS_N_CTX: int | None = None


class StubRouterChat(BaseHTTPRequestHandler):
    """The router's OpenAI chat endpoint, streaming its reply as SSE.

    The local runtime speaks OpenAI now, so the adapter composes the same
    provider a remote endpoint uses and this stub is shaped accordingly.
    """

    def do_GET(self) -> None:
        if self.path == "/models":
            self._send(
                json.dumps(
                    {
                        "object": "list",
                        "data": [
                            {"id": "Qwen3-4B-Q4_K_M", "status": {"value": "loaded"}}
                        ],
                    }
                ).encode()
            )
        elif self.path.startswith("/props"):
            settings = (
                {"n_ctx": _PROPS_N_CTX} if _PROPS_N_CTX is not None else {}
            )
            self._send(
                json.dumps({"default_generation_settings": settings}).encode()
            )
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path not in ("/v1/chat/completions", "/models/load"):
            self.send_error(404)
            return
        if self.path == "/models/load":
            self._send(b'{"success": true}')
            return

        request = json.loads(raw)
        _REQUESTS.append(request)
        deltas = (
            ["Revenue ", "Growth"]
            if request.get("max_tokens") == 12
            else REPLY_DELTAS
        )
        chunks = [
            "data: " + json.dumps({"choices": [{"delta": {"content": delta}}]})
            for delta in deltas
        ] + ["data: [DONE]"]
        self._send(("\n\n".join(chunks) + "\n\n").encode())

    def _send(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def llamacpp_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict]]:
    """A real llama-server stand-in on a real port; yields the requests it sees."""
    global _PROPS_N_CTX
    _REQUESTS.clear()
    _PROPS_N_CTX = None
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubRouterChat)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_llm_settings(), "llamacpp_base_url", url)

    yield _REQUESTS

    server.shutdown()
    server.server_close()


class StubRouterUnauthorized(BaseHTTPRequestHandler):
    """A router that always answers 401, as if the connection were bad.

    It still answers `GET /models`, because the adapter checks residency before
    it asks a question and a 501 there would fail the request for the wrong
    reason entirely.
    """

    def do_GET(self) -> None:
        body = b'{"object": "list", "data": []}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers["Content-Length"]))
        body = b'{"error": "unauthorized"}'
        self.send_response(401)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


def set_props_n_ctx(n_ctx: int) -> None:
    """Make the next `llamacpp_server` request report this context window."""
    global _PROPS_N_CTX
    _PROPS_N_CTX = n_ctx


@pytest.fixture
def llamacpp_server_unauthorized(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A chat stand-in that fails every request, for exercising error handling."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubRouterUnauthorized)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_llm_settings(), "llamacpp_base_url", url)

    yield

    server.shutdown()
    server.server_close()
