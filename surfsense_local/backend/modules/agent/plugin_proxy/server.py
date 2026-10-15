"""The proxy opencode's outbound connections go through: a tunnel to a ready plugin's host, and nothing else.

Only `CONNECT` passes, so opencode's TLS reaches the plugin untouched and SurfSense
sees the host, never the content. Everything else opencode might fetch is refused,
as the discard port it pointed at before refused it.
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from modules.agent.plugin_proxy.allowed_hosts import AllowedHosts

# A request line and its headers; a client that sends more, or takes longer, is not opencode.
_HEAD_BYTES = 8192
_HEAD_SECONDS = 10
# A host that takes longer to accept is answered 502, so opencode fails the call at once.
CONNECT_SECONDS = 10
# The host's next address is tried this long after the last, not once it fails: an IPv6
# address that cannot be reached cost each tunnel to `localhost` 2 s on Windows.
_NEXT_ADDRESS_SECONDS = 0.25
_CHUNK = 65536

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def serving_plugin_proxy(
    sessions: sessionmaker[Session], host: str, port: int
) -> AsyncIterator[int]:
    """The proxy on `host`, yielding the port it listens on."""
    allowed = AllowedHosts(sessions)
    # Last-call records in flight, held so none is collected before it ran.
    recording: set[asyncio.Task[None]] = set()

    async def handle(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            await _tunnel(allowed, recording, reader, writer)
        except (
            OSError,
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
            TimeoutError,
        ):
            logger.debug("a plugin connection ended", exc_info=True)
        except Exception:
            logger.warning("a plugin connection failed", exc_info=True)
        finally:
            writer.close()

    server = await asyncio.start_server(handle, host, port, limit=_HEAD_BYTES)
    async with server:
        yield server.sockets[0].getsockname()[1]


async def _tunnel(
    allowed: AllowedHosts,
    recording: set[asyncio.Task[None]],
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), _HEAD_SECONDS)
    method, target, *_ = head.split(b"\r\n", 1)[0].decode("latin-1").split(" ")
    host, _, port = target.rpartition(":")
    host = host.strip("[]").lower()
    started = time.perf_counter()
    # Any failure before the answer gets one: a socket closed unanswered fails the
    # call only after opencode's own wait, and reads as a silent drop.
    try:
        ready = method == "CONNECT" and port.isdigit()
        if ready:
            hosts = allowed.current()
            if hosts is None:
                hosts = await run_in_threadpool(allowed.read)
            ready = (host, int(port)) in hosts
    except Exception:
        logger.warning(
            "could not check opencode's %s %s", method, target, exc_info=True
        )
        await _answer(writer, b"502 Bad Gateway")
        return
    checked = time.perf_counter()
    if not ready:
        logger.info("refused opencode's %s %s", method, target)
        await _answer(writer, b"403 Forbidden")
        return
    try:
        upstream_reader, upstream_writer = await asyncio.wait_for(
            asyncio.open_connection(
                host, int(port), happy_eyeballs_delay=_NEXT_ADDRESS_SECONDS
            ),
            CONNECT_SECONDS,
        )
    except (OSError, TimeoutError):
        logger.warning("could not reach %s for opencode", target, exc_info=True)
        await _answer(writer, b"502 Bad Gateway")
        return
    connected = time.perf_counter()
    logger.info(
        "tunnel to %s:%s: checked in %.0f ms, connected in %.0f ms",
        host,
        port,
        (checked - started) * 1000,
        (connected - checked) * 1000,
    )
    # Closed here as well as by its pipe: opencode gone before its 200, or a cancel,
    # would otherwise leave the host's connection open until it is collected.
    try:
        if (destination := allowed.call_to_record(host)) is not None:
            task = asyncio.create_task(_record_call(allowed, destination))
            recording.add(task)
            task.add_done_callback(recording.discard)
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await writer.drain()
        sent, received = await asyncio.gather(
            _pipe(reader, upstream_writer), _pipe(upstream_reader, writer)
        )
    finally:
        upstream_writer.close()
    logger.info(
        "tunnel to %s:%s closed: %d bytes out, %d in, %.1f s",
        host,
        port,
        sent,
        received,
        time.perf_counter() - connected,
    )


async def _answer(writer: asyncio.StreamWriter, status: bytes) -> None:
    writer.write(b"HTTP/1.1 " + status + b"\r\nContent-Length: 0\r\n\r\n")
    await writer.drain()


async def _record_call(allowed: AllowedHosts, destination: str) -> None:
    """Off the tunnel's path: a busy database delays the record, never the call."""
    try:
        await run_in_threadpool(allowed.record_call, destination)
    except Exception:
        logger.warning("could not record a call to %s", destination, exc_info=True)


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> int:
    """Copy until either side closes; the bytes copied."""
    copied = 0
    try:
        while data := await reader.read(_CHUNK):
            writer.write(data)
            await writer.drain()
            copied += len(data)
    except OSError:
        pass
    finally:
        writer.close()
    return copied
