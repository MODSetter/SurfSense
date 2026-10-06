from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse


def event_stream(frames: AsyncIterator[bytes]) -> StreamingResponse:
    """A run's frames as server-sent events."""
    return StreamingResponse(
        frames,
        media_type="text/event-stream",
        # Keep a proxy from buffering or caching a live stream into one late blob.
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
