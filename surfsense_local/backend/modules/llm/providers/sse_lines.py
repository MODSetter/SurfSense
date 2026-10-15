"""A server-sent event stream's lines, split only where a line ends.

httpx's `aiter_lines` splits as `str.splitlines` does, so U+2028, U+2029 and
U+0085, which opencode and llama-server leave raw inside a JSON string, would
cut one event in two. SSE ends a line with a line feed, optionally after a
carriage return; none of our upstreams ends one with a carriage return alone.
"""

from collections.abc import AsyncIterable, AsyncIterator

import httpx


class Lines:
    """Text in as it arrives, whole lines out, without their endings."""

    def __init__(self) -> None:
        # The line being read, kept in pieces so a long one is joined once.
        self._pending: list[str] = []

    def feed(self, text: str) -> list[str]:
        """The lines `text` completes."""
        *complete, rest = text.split("\n")
        if complete:
            complete[0] = "".join(self._pending) + complete[0]
            self._pending = []
        if rest:
            self._pending.append(rest)
        return [line.removesuffix("\r") for line in complete]

    def close(self) -> list[str]:
        """The last line, when the stream ended without a line feed."""
        last = "".join(self._pending).removesuffix("\r")
        self._pending = []
        return [last] if last else []


async def sse_lines(reply: httpx.Response) -> AsyncIterator[str]:
    """The reply's lines as they arrive, in place of `reply.aiter_lines()`."""
    lines = Lines()
    async for text in reply.aiter_text():
        for line in lines.feed(text):
            yield line
    for line in lines.close():
        yield line


async def whole_lines(chunks: AsyncIterable[bytes]) -> AsyncIterator[bytes]:
    """The bytes unchanged, each read cut after its last line feed, so a stream
    that breaks never leaves half a line ahead of what follows it."""
    pending: list[bytes] = []
    async for chunk in chunks:
        cut = chunk.rfind(b"\n") + 1
        if not cut:
            pending.append(chunk)
            continue
        yield b"".join(pending) + chunk[:cut]
        pending = [chunk[cut:]] if cut < len(chunk) else []
    if pending:
        yield b"".join(pending)
