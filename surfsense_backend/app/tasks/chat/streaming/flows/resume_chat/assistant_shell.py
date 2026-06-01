"""Pre-write a fresh assistant row for this resume turn.

The original (interrupted) ``stream_new_chat`` invocation already persisted
its own assistant row anchored to a different ``turn_id``; resume allocates a
new ``turn_id`` (per-request, see ``orchestrator``) so we need a separate row
keyed on the same ``(thread_id, turn_id, ASSISTANT)`` invariant.

Idempotent against migration 141's partial unique index — recovers the
existing id on retry.

Resume does NOT emit ``data-user-message-id``: the user row is from the
original interrupted turn (different ``turn_id``) and is never re-persisted
here. See B5 in the ``sse-based_message_id_handshake`` plan.
"""

from __future__ import annotations

from app.tasks.chat.persistence import persist_assistant_shell


async def persist_resume_assistant_shell(
    *,
    chat_id: int,
    user_id: str | None,
    turn_id: str,
) -> int | None:
    return await persist_assistant_shell(
        chat_id=chat_id,
        user_id=user_id,
        turn_id=turn_id,
    )
