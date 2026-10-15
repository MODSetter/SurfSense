"""Real sockets on 127.0.0.1 for the transport tests; nothing leaves the machine.

:class:`LocalServer` speaks enough HTTP/1.1 keep-alive to answer curl directly or
as a plain-HTTP proxy (absolute-URI requests). :class:`Blackhole` accepts
connections and never answers, like a dead residential exit.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from urllib.parse import parse_qs, urlsplit


class LocalServer:
    """Routes by path; counts connections and the requests in flight at once."""

    def __init__(self, *, slow_first_s: float = 0.0) -> None:
        self.connections = 0
        self.open_connections = 0
        self.inflight = 0
        self.max_inflight = 0
        self.requests: list[dict] = []
        # The first request served waits this long (a slow first exit).
        self.slow_first_s = slow_first_s
        self._served = 0
        self._server: asyncio.Server | None = None
        self.port = 0

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def __aenter__(self) -> LocalServer:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc: object) -> None:
        assert self._server is not None
        self._server.close()
        # Do not wait_closed(): curl may still hold an idle keep-alive socket open.

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.connections += 1
        self.open_connections += 1
        try:
            while True:
                head = await reader.readuntil(b"\r\n\r\n")
                lines = head.decode("latin-1").split("\r\n")
                method, target, _ = lines[0].split(" ", 2)
                headers = {}
                for line in lines[1:]:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        headers[k.strip().lower()] = v.strip()
                body = b""
                if int(headers.get("content-length", "0")):
                    body = await reader.readexactly(int(headers["content-length"]))
                parts = urlsplit(target)
                self.requests.append(
                    {
                        "method": method,
                        "target": target,
                        "path": parts.path,
                        "headers": headers,
                        "body": body,
                    }
                )
                self._served += 1
                if self._served == 1 and self.slow_first_s:
                    # Wait like a slow exit, but notice a client that hangs up.
                    try:
                        gone = not await asyncio.wait_for(
                            reader.read(1), self.slow_first_s
                        )
                    except TimeoutError:
                        gone = False
                    if gone:
                        return
                self.inflight += 1
                self.max_inflight = max(self.max_inflight, self.inflight)
                try:
                    status, extra, payload = await self._route(
                        parts.path, parse_qs(parts.query), headers
                    )
                finally:
                    self.inflight -= 1
                out = [f"HTTP/1.1 {status} X", f"Content-Length: {len(payload)}"]
                out += [f"{k}: {v}" for k, v in extra]
                writer.write(("\r\n".join(out) + "\r\n\r\n").encode() + payload)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            self.open_connections -= 1
            writer.close()

    async def _route(
        self, path: str, query: dict[str, list[str]], headers: dict[str, str]
    ) -> tuple[int, list[tuple[str, str]], bytes]:
        if path == "/ok":
            return (
                200,
                [
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Set-Cookie", "a=1; Path=/"),
                ],
                b"hello",
            )
        if path == "/latin":
            return (
                200,
                [("Content-Type", "text/html; charset=iso-8859-1")],
                "café".encode("latin-1"),
            )
        if path == "/json":
            return 200, [("Content-Type", "application/json")], b'{"a": [1, 2]}'
        if path == "/redirect":
            return 302, [("Location", "/ok")], b""
        if path == "/slow":
            await asyncio.sleep(float(query.get("s", ["0.3"])[0]))
            return 200, [], b"slow"
        if path.startswith("/status/"):
            return int(path.rsplit("/", 1)[1]), [], b"refused"
        if path == "/echo":
            return (
                200,
                [("Content-Type", "application/json")],
                json.dumps(headers).encode(),
            )
        return 404, [], b""


class Blackhole:
    """Accepts every connection and never sends a byte."""

    def __init__(self) -> None:
        self.connections = 0
        self._server: asyncio.Server | None = None
        self._writers: list[asyncio.StreamWriter] = []
        self.port = 0

    @property
    def proxy(self) -> str:
        return f"http://user:pa55word@127.0.0.1:{self.port}"  # pragma: allowlist secret

    async def __aenter__(self) -> Blackhole:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc: object) -> None:
        assert self._server is not None
        self._server.close()
        for writer in self._writers:
            writer.close()

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.connections += 1
        self._writers.append(writer)
        with suppress(ConnectionError):
            await reader.read()  # until the client gives up and closes
