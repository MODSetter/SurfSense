"""Reasoning-block streaming events."""

from __future__ import annotations

from datetime import UTC, datetime

from ..emitter import Emitter, attach_emitted_by
from ..envelope import format_sse


def format_reasoning_start(reasoning_id: str, *, emitter: Emitter | None = None) -> str:
    return format_sse(
        attach_emitted_by(
            {
                "type": "reasoning-start",
                "id": reasoning_id,
                "startedAt": datetime.now(UTC).isoformat(),
            },
            emitter,
        )
    )


def format_reasoning_delta(
    reasoning_id: str,
    delta: str,
    *,
    emitter: Emitter | None = None,
) -> str:
    return format_sse(
        attach_emitted_by(
            {"type": "reasoning-delta", "id": reasoning_id, "delta": delta},
            emitter,
        )
    )


def format_reasoning_end(reasoning_id: str, *, emitter: Emitter | None = None) -> str:
    return format_sse(
        attach_emitted_by(
            {
                "type": "reasoning-end",
                "id": reasoning_id,
                "completedAt": datetime.now(UTC).isoformat(),
            },
            emitter,
        )
    )
