from collections.abc import AsyncIterator

import httpx

from modules.agent.opencode_client.payloads import Event
from modules.llm.providers.sse_lines import sse_lines

# opencode sends a heartbeat every 15 s, so well past twice that without a byte
# means the stream is dead even though the socket is open. The read raises, and
# the caller reconnects and reads the state again: frames carry no id to resume from.
SILENCE_SECONDS = 40.0
_STREAM_TIMEOUT = httpx.Timeout(10.0, read=SILENCE_SECONDS)


async def read_events(http: httpx.AsyncClient) -> AsyncIterator[Event]:
    """Every folder's events as opencode sends them; heartbeats are comments, left out."""
    async with http.stream("GET", "/api/event", timeout=_STREAM_TIMEOUT) as reply:
        reply.raise_for_status()
        async for line in sse_lines(reply):
            if line.startswith("data:"):
                yield Event.model_validate_json(line.removeprefix("data:").strip())
