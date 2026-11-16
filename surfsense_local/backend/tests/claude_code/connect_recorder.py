"""A proxy that tunnels Anthropic's two hosts, refuses every other, and records each CONNECT."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from modules.llm.subscriptions.claude.hosts import CLAUDE_HOSTS


@dataclass
class Recorded:
    url: str = ""
    connects: list[tuple[str, bool]] = field(default_factory=list)


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except OSError:
        pass
    finally:
        writer.close()


@contextlib.asynccontextmanager
async def recording_proxy() -> AsyncIterator[Recorded]:
    """Serve it on a free loopback port for the length of the block."""
    recorded = Recorded()

    async def handle(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        request = await reader.readline()
        while (await reader.readline()) not in (b"\r\n", b""):
            pass
        method, target, *_ = [*request.decode().split(), "", ""]
        host, _, port = target.rpartition(":")
        allowed = method == "CONNECT" and host in CLAUDE_HOSTS
        recorded.connects.append((target, allowed))
        if not allowed:
            writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        upstream_reader, upstream_writer = await asyncio.open_connection(
            host, int(port)
        )
        writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        await writer.drain()
        await asyncio.gather(
            _pipe(reader, upstream_writer), _pipe(upstream_reader, writer)
        )

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    recorded.url = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
    async with server:
        yield recorded
