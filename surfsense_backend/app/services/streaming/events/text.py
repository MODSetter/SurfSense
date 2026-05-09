"""Text-block streaming events."""

from __future__ import annotations

from ..emitter import Emitter, attach_emitted_by
from ..envelope import format_sse


def format_text_start(text_id: str, *, emitter: Emitter | None = None) -> str:
    return format_sse(
        attach_emitted_by({"type": "text-start", "id": text_id}, emitter)
    )


def format_text_delta(
    text_id: str,
    delta: str,
    *,
    emitter: Emitter | None = None,
) -> str:
    return format_sse(
        attach_emitted_by(
            {"type": "text-delta", "id": text_id, "delta": delta}, emitter
        )
    )


def format_text_end(text_id: str, *, emitter: Emitter | None = None) -> str:
    return format_sse(
        attach_emitted_by({"type": "text-end", "id": text_id}, emitter)
    )
