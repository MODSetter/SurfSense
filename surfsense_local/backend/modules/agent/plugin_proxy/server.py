"""The proxy opencode's outbound connections go through: a tunnel to a ready plugin's host, and nothing else.

Only `CONNECT` passes, so opencode's TLS reaches the plugin untouched and SurfSense
sees the host, never the content. Everything else opencode might fetch is refused,
as the discard port it pointed at before refused it.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from modules.agent.plugin_proxy.allowed_hosts import may_connect

# A request line and its headers; a client that sends more, or takes longer, is not opencode.
_HEAD_BYTES = 8192
_HEAD_SECONDS = 10
_CHUNK = 65536

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def serving_plugin_proxy(
    sessions: sessionmaker[Session], host: str, port: int
) -> AsyncIterator[int]:
    """The proxy on `host`, yielding the port it listens on."""

    async def handle(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            await _tunnel(sessions, reader, writer)
        except (
            OSError,
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
            TimeoutError,
        ):
            logger.debug("a plugin connection ended", exc_info=True)
        finally:
            writer.close()

    server = await asyncio.start_server(handle, host, port, limit=_HEAD_BYTES)
    async with server:
        yield server.sockets[0].getsockname()[1]


async def _tunnel(
    sessions: sessionmaker[Session],
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), _HEAD_SECONDS)
    method, target, *_ = head.split(b"\r\n", 1)[0].decode("latin-1").split(" ")
    host, _, port = target.rpartition(":")
    allowed = (
        method == "CONNECT"
        and port.isdigit()
        and await run_in_threadpool(_may_connect, sessions, host.strip("[]"), int(port))
    )
    if not allowed:
        logger.info("refused opencode's %s %s", method, target)
        writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        return
    upstream_reader, upstream_writer = await asyncio.open_connection(host, int(port))
    writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
    await writer.drain()
    await asyncio.gather(_pipe(reader, upstream_writer), _pipe(upstream_reader, writer))


def _may_connect(sessions: sessionmaker[Session], host: str, port: int) -> bool:
    with sessions() as session:
        allowed = may_connect(session, host, port)
        session.commit()
        return allowed


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(_CHUNK):
            writer.write(data)
            await writer.drain()
    except OSError:
        pass
    finally:
        writer.close()
