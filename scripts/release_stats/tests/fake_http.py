"""An opener that answers urllib requests from a table, as GitHub or PostHog would."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class FakeResponse:
    def __init__(self, body: Any, link: str | None = None) -> None:
        self._body = json.dumps(body).encode()
        self.headers = {"Link": link} if link else {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class FakeOpener:
    """Answers each URL with ``(body, link)``, or raises its status if it is an int."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
        self.requests.append(request)
        answer = self.routes.get(request.full_url, ({}, None))
        if isinstance(answer, int):
            raise urllib.error.HTTPError(request.full_url, answer, "refused", {}, None)
        body, link = answer
        return FakeResponse(body, link)


class LocalServer:
    """A real server on 127.0.0.1, for what urllib does on its own, such as redirects.

    Answers a path in ``redirects`` with a 302 to its URL, any other with ``[]``,
    and records each request's path and Authorization header in ``seen``.
    """

    def __init__(self) -> None:
        self.redirects: dict[str, str] = {}
        self.seen: list[tuple[str, str | None]] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                server.seen.append((self.path, self.headers.get("Authorization")))
                location = server.redirects.get(self.path)
                body = b"" if location else b"[]"
                self.send_response(302 if location else 200)
                if location:
                    self.send_header("Location", location)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: object) -> None:
                return None

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def __enter__(self) -> LocalServer:
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *_: object) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
