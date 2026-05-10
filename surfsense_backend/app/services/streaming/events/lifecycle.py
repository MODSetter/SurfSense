"""High-level message and step lifecycle events.

Wire verbs are fixed by the AI SDK protocol (``start`` / ``finish`` for
the whole message, ``start-step`` / ``finish-step`` for each step).
Python helpers always read ``format_<entity>_<verb>`` so pairs are
visible at the call site.
"""

from __future__ import annotations

from ..emitter import Emitter, attach_emitted_by
from ..envelope import format_sse


def format_message_start(message_id: str, *, emitter: Emitter | None = None) -> str:
    payload = {"type": "start", "messageId": message_id}
    return format_sse(attach_emitted_by(payload, emitter))


def format_message_finish(*, emitter: Emitter | None = None) -> str:
    return format_sse(attach_emitted_by({"type": "finish"}, emitter))


def format_step_start(*, emitter: Emitter | None = None) -> str:
    return format_sse(attach_emitted_by({"type": "start-step"}, emitter))


def format_step_finish(*, emitter: Emitter | None = None) -> str:
    return format_sse(attach_emitted_by({"type": "finish-step"}, emitter))
