"""What the router is doing with a model, as it does it.

`GET /models/sse` streams a frame every time a model's status changes, carrying
the stage being loaded and how far through it the runtime is. Subscribing means
the API stops inferring runtime state from polls and reads it instead.

The alternative was a timer and a guess. A cold load is tens of seconds, which
is long enough that a caller with no progress to report has to choose between a
silent wait and an invented one.
"""

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# No read timeout: this stream is idle whenever nothing is loading, which is
# most of the time, and an idle stream is the healthy state rather than a stall.
TIMEOUT = httpx.Timeout(None, connect=5.0)


@dataclass(frozen=True)
class LoadProgress:
    """One model's state, at one moment.

    `value` and `stage` are absent until the runtime has a figure to report, so
    a caller renders an unknown duration rather than a zero.
    """

    model_id: str
    status: str
    stage: str | None = None
    value: float | None = None


async def watch_models(
    base_url: str, *, transport: httpx.BaseTransport | None = None
) -> AsyncIterator[LoadProgress]:
    """Every status change the router announces, until the stream ends.

    Ends when the sidecar goes away, which is routine rather than exceptional:
    a preset rewrite restarts it. A caller that wants to keep watching
    resubscribes.
    """
    async with (
        httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=TIMEOUT, transport=transport
        ) as client,
        client.stream("GET", "/models/sse") as reply,
    ):
        reply.raise_for_status()
        async for line in reply.aiter_lines():
            progress = _progress(line)
            if progress is not None:
                yield progress


def _progress(line: str) -> LoadProgress | None:
    """One frame, or None for anything that is not one.

    SSE carries comments and keepalives, and a stream that outlives the load it
    is reporting has to ignore them rather than end on the first one.
    """
    if not line.startswith("data:"):
        return None
    payload = line[len("data:") :].strip()
    if not payload:
        return None
    try:
        frame = json.loads(payload)
    except ValueError:
        logger.debug("ignoring an unparseable model event")
        return None
    if not isinstance(frame, dict):
        return None

    data = frame.get("data")
    data = data if isinstance(data, dict) else {}
    status = data.get("status")
    model_id = frame.get("model")
    if not isinstance(status, str) or not isinstance(model_id, str):
        return None

    reported = data.get("progress")
    reported = reported if isinstance(reported, dict) else {}
    value = reported.get("value")
    stage = reported.get("current")
    return LoadProgress(
        model_id=model_id,
        status=status,
        stage=stage if isinstance(stage, str) else None,
        value=float(value) if isinstance(value, int | float) else None,
    )
