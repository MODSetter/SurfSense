import asyncio
import contextlib
from urllib.parse import parse_qs, urlsplit

from modules.llm.subscriptions.chatgpt.endpoints import CALLBACK_PATH

# Shown in the browser tab the sign-in ends in; the app itself says what happened.
_DONE_PAGE = (
    b"<!doctype html><meta charset=utf-8><title>SurfSense</title>"
    b"<body style='font-family:system-ui;padding:3rem'>"
    b"<h1>You can close this tab</h1><p>Return to SurfSense to finish.</p>"
)
_MAX_REQUEST_LINE = 8192


class Loopback:
    """A one-shot HTTP listener on 127.0.0.1 that catches the OAuth redirect.

    Its own random port, not the API's: OpenAI allows any port on 127.0.0.1
    as long as scheme, host and path match what the sign-in asked for.
    """

    def __init__(self) -> None:
        self._callback: asyncio.Future[dict[str, str]] = (
            asyncio.get_running_loop().create_future()
        )
        self._server: asyncio.Server | None = None

    async def open(self) -> str:
        """Start listening and return the redirect URI to hand OpenAI."""
        self._server = await asyncio.start_server(self._serve, "127.0.0.1", 0)
        port = self._server.sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}{CALLBACK_PATH}"

    async def callback(self) -> dict[str, str]:
        """The query of the first request to the callback path."""
        return await self._callback

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
        if not self._callback.done():
            self._callback.cancel()

    async def _serve(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            line = await asyncio.wait_for(reader.readline(), 10)
            parts = line[:_MAX_REQUEST_LINE].decode("latin-1").split()
            target = (
                urlsplit(parts[1]) if len(parts) >= 2 and parts[0] == "GET" else None
            )
            if target is None or target.path != CALLBACK_PATH:
                writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
                return
            if not self._callback.done():
                query = {k: v[0] for k, v in parse_qs(target.query).items()}
                self._callback.set_result(query)
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                b"Content-Length: %d\r\nConnection: close\r\n\r\n%s"
                % (len(_DONE_PAGE), _DONE_PAGE)
            )
        except (TimeoutError, ConnectionError, UnicodeDecodeError):
            pass
        finally:
            with contextlib.suppress(ConnectionError):
                await writer.drain()
            writer.close()
