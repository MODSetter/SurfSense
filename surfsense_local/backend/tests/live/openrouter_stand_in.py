"""OpenRouter's public model listing on a loopback port, for tests that price a model without the network."""

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@contextmanager
def serve_listing(models: list[dict[str, Any]]) -> Iterator[str]:
    """Yields the listing's URL while it serves these entries."""
    body = json.dumps({"data": models}).encode()

    class _Listing(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            """Keep the request log out of the test output."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Listing)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/v1/models"
    finally:
        server.shutdown()
        server.server_close()
