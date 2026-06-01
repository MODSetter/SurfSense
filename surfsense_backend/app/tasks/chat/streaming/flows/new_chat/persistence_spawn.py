"""Concurrent persistence tasks spawned right after the initial validation gate.

These run *during* the rest of the pre-stream setup so we don't serialize
their latency against agent construction. Awaiting them at the SSE message-id
yield sites preserves the ghost-thread protection (the user-row INSERT must
succeed before any LLM streaming begins).

The ``set_ai_responding`` flag flip runs fully fire-and-forget on its own
shielded session — failures only delay the "AI is responding…" UI flag, not
the response itself.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from app.db import shielded_async_session
from app.services.chat_session_state_service import set_ai_responding
from app.tasks.chat.persistence import (
    persist_assistant_shell,
    persist_user_turn,
)

logger = logging.getLogger(__name__)


def spawn_set_ai_responding_bg(
    *,
    chat_id: int,
    user_id: str | None,
    background_tasks: set[asyncio.Task[Any]],
) -> None:
    """Fire-and-forget: flip the per-thread AI-responding flag on its own session.

    Errors are swallowed and logged — the worst case is a stale UI flag, which
    is preferable to delaying the SSE stream behind a flag write.
    """
    if not user_id:
        return

    async def _bg_set_ai_responding() -> None:
        try:
            async with shielded_async_session() as s:
                await set_ai_responding(s, chat_id, UUID(user_id))
        except Exception:
            logger.warning(
                "set_ai_responding failed (chat_id=%s)",
                chat_id,
                exc_info=True,
            )

    t = asyncio.create_task(_bg_set_ai_responding())
    background_tasks.add(t)
    t.add_done_callback(background_tasks.discard)


def spawn_persist_user_task(
    *,
    chat_id: int,
    user_id: str | None,
    turn_id: str,
    user_query: str,
    user_image_data_urls: list[str] | None,
    mentioned_documents: list[dict[str, Any]] | None,
    background_tasks: set[asyncio.Task[Any]],
) -> asyncio.Task[int | None]:
    """Spawn the user-row INSERT; await at the user-message-id yield site."""
    task = asyncio.create_task(
        persist_user_turn(
            chat_id=chat_id,
            user_id=user_id,
            turn_id=turn_id,
            user_query=user_query,
            user_image_data_urls=user_image_data_urls,
            mentioned_documents=mentioned_documents,
        )
    )
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task


def spawn_persist_assistant_shell_task(
    *,
    chat_id: int,
    user_id: str | None,
    turn_id: str,
    background_tasks: set[asyncio.Task[Any]],
) -> asyncio.Task[int | None]:
    """Spawn the assistant-shell INSERT; await at the assistant-message-id yield site."""
    task = asyncio.create_task(
        persist_assistant_shell(
            chat_id=chat_id,
            user_id=user_id,
            turn_id=turn_id,
        )
    )
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task


async def await_persist_task(
    task: asyncio.Task[int | None] | None,
    *,
    chat_id: int,
    turn_id: str,
    log_label: str,
) -> int | None:
    """Join a spawned persistence task with ``shield`` + uniform error handling.

    ``shield`` keeps the DB write alive if the SSE generator is cancelled by
    client disconnect mid-await. Returns ``None`` on failure; the caller
    abort-paths the turn with a friendly error SSE.
    """
    if task is None:
        return None
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(
            "%s failed (chat_id=%s, turn_id=%s)", log_label, chat_id, turn_id
        )
        return None
