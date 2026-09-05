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


class StubOllamaChat(BaseHTTPRequestHandler):
    """Just the chat endpoint of Ollama's native API, streaming its reply."""

    def do_POST(self) -> None:
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path != "/api/chat":
            self.send_error(404)
            return

        _REQUESTS.append(json.loads(raw))
        body = "".join(
            json.dumps({"message": {"content": delta}}) + "\n"
            for delta in REPLY_DELTAS
        ).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def ollama_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict]]:
    """A real Ollama chat stand-in on a real port; yields the requests it sees."""
    _REQUESTS.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubOllamaChat)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_llm_settings(), "ollama_base_url", url)

    yield _REQUESTS

    server.shutdown()
    server.server_close()
