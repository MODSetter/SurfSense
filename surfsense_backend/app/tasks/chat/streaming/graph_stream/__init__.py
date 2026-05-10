"""LangGraph ``astream_events`` → SSE (``stream_output`` + ``StreamingResult``).

Imports are lazy to avoid a circular import with ``relay.event_relay``.
"""

from __future__ import annotations

__all__ = ["StreamingResult", "stream_output"]


def __getattr__(name: str):
    if name == "stream_output":
        from app.tasks.chat.streaming.graph_stream.event_stream import stream_output

        return stream_output
    if name == "StreamingResult":
        from app.tasks.chat.streaming.graph_stream.result import StreamingResult

        return StreamingResult
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
