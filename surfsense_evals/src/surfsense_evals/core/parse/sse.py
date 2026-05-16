"""Minimal SSE consumer compatible with SurfSense's wire format.

SurfSense uses ``app/services/streaming/envelope/sse.py`` to frame events:

* ``data: <single-line-string>\\n\\n``
* ``data: <json-string>\\n\\n``  (most events)
* ``data: [DONE]\\n\\n``  (terminator)

There is no ``event:``, ``id:``, or ``retry:`` framing in production —
``format_sse(payload)`` only emits the ``data:`` line. This implementation
is therefore intentionally smaller than ``httpx-sse`` (which we still
list as a dep so callers who want richer parsing can opt in): one event
per ``data:`` line, separated by blank lines.

We accept any line iterator (an ``httpx.Response.aiter_lines`` adapter
in production, a list in tests) so this is unit-testable without a
network mock.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class SseEvent:
    """A parsed SSE event. Only the ``data`` field is populated.

    Multi-line payloads (``data: a\\ndata: b``) are joined with ``\\n``
    per the SSE spec, even though SurfSense doesn't currently emit them.
    """

    data: str


async def iter_sse_events(lines: AsyncIterator[str]) -> AsyncIterator[SseEvent]:
    """Yield one ``SseEvent`` per blank-line-terminated frame.

    Lines that are empty or whitespace flush the buffer. ``data:`` lines
    are accumulated into the buffer; everything else is ignored
    (matches the lenient browser EventSource behaviour).
    """

    buffer: list[str] = []
    async for raw in lines:
        if raw is None:
            continue
        line = raw.rstrip("\r")
        if line == "":
            if buffer:
                yield SseEvent(data="\n".join(buffer))
                buffer.clear()
            continue
        if line.startswith(":"):
            # comment / heartbeat
            continue
        if line.startswith("data:"):
            # spec: optional single space after the colon.
            payload = line[5:]
            if payload.startswith(" "):
                payload = payload[1:]
            buffer.append(payload)
            continue
        # Any other field (event:, id:, retry:) is currently unused.
        continue

    if buffer:
        yield SseEvent(data="\n".join(buffer))


__all__ = ["SseEvent", "iter_sse_events"]
