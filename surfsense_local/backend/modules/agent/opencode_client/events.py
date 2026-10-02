from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from modules.agent.opencode_client.payloads import Event

# opencode sends a heartbeat every 10 s, so twice that without a byte means the
# stream is dead even though the socket is open. The read raises, and the
# caller reconnects and reads the state again: frames carry no id to resume from.
SILENCE_SECONDS = 20.0
_STREAM_TIMEOUT = httpx.Timeout(10.0, read=SILENCE_SECONDS)


async def read_events(http: httpx.AsyncClient, directory: Path) -> AsyncIterator[Event]:
    """One folder's events as opencode sends them, heartbeats left out."""
    async with http.stream(
        "GET", "/event", params={"directory": str(directory)}, timeout=_STREAM_TIMEOUT
    ) as reply:
        reply.raise_for_status()
        async for line in reply.aiter_lines():
            if not line.startswith("data:"):
                continue
            event = Event.model_validate_json(line.removeprefix("data:").strip())
            if event.type != "server.heartbeat":
                yield event
