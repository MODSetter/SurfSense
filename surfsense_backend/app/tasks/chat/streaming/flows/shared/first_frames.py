"""Initial SSE frames every flow emits right after pre-stream setup.

Order matters: ``message_start`` opens the assistant message, ``start_step``
opens the first thinking step, ``turn-info`` lets the frontend stamp the
correlation id onto the in-flight message, and ``turn-status: busy`` flips the
UI into the streaming state.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.services.new_streaming_service import VercelStreamingService


def iter_initial_frames(
    streaming_service: VercelStreamingService,
    *,
    turn_id: str,
) -> Iterator[str]:
    """Yield the four canonical opening frames in order.

    ``turn-info`` carries ``chat_turn_id`` so even pure-text turns (which
    never produce a tool / action-log event) still teach the frontend the
    turn correlation id used for ``appendMessage`` durable storage.
    """
    yield streaming_service.format_message_start()
    yield streaming_service.format_start_step()
    yield streaming_service.format_data("turn-info", {"chat_turn_id": turn_id})
    yield streaming_service.format_data("turn-status", {"status": "busy"})


def iter_final_frames(
    streaming_service: VercelStreamingService,
) -> Iterator[str]:
    """Yield ``turn-status: idle`` plus the finish/done trailer in order."""
    yield streaming_service.format_data("turn-status", {"status": "idle"})
    yield streaming_service.format_finish_step()
    yield streaming_service.format_finish()
    yield streaming_service.format_done()
