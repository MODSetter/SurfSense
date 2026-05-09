"""Generic ``data-*`` envelopes and SurfSense-specific data parts.

Inner ``data`` dict fields use snake_case. Legacy ``threadId`` /
``messageId`` keys are preserved where they cross the AI SDK boundary.
"""

from __future__ import annotations

from typing import Any

from ..emitter import Emitter, attach_emitted_by
from ..envelope import format_sse


def format_data(
    data_type: str,
    data: Any,
    *,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = {"type": f"data-{data_type}", "data": data}
    return format_sse(attach_emitted_by(payload, emitter))


def format_terminal_info(
    text: str,
    *,
    message_type: str = "info",
    emitter: Emitter | None = None,
) -> str:
    return format_data(
        "terminal-info",
        {"text": text, "type": message_type},
        emitter=emitter,
    )


def format_further_questions(
    questions: list[str],
    *,
    emitter: Emitter | None = None,
) -> str:
    return format_data("further-questions", {"questions": questions}, emitter=emitter)


def format_thinking_step(
    *,
    step_id: str,
    title: str,
    status: str = "in_progress",
    items: list[str] | None = None,
    emitter: Emitter | None = None,
) -> str:
    return format_data(
        "thinking-step",
        {
            "id": step_id,
            "title": title,
            "status": status,
            "items": items or [],
        },
        emitter=emitter,
    )


def format_thread_title_update(
    *,
    thread_id: int,
    title: str,
    emitter: Emitter | None = None,
) -> str:
    return format_data(
        "thread-title-update",
        {"threadId": thread_id, "title": title},
        emitter=emitter,
    )


def format_turn_info(
    *,
    chat_turn_id: str,
    emitter: Emitter | None = None,
) -> str:
    return format_data("turn-info", {"chat_turn_id": chat_turn_id}, emitter=emitter)


def format_turn_status(
    *,
    status: str,
    emitter: Emitter | None = None,
) -> str:
    return format_data("turn-status", {"status": status}, emitter=emitter)


def format_user_message_id(
    *,
    message_id: str,
    turn_id: str,
    emitter: Emitter | None = None,
) -> str:
    return format_data(
        "user-message-id",
        {"message_id": message_id, "turn_id": turn_id},
        emitter=emitter,
    )


def format_assistant_message_id(
    *,
    message_id: str,
    turn_id: str,
    emitter: Emitter | None = None,
) -> str:
    return format_data(
        "assistant-message-id",
        {"message_id": message_id, "turn_id": turn_id},
        emitter=emitter,
    )
