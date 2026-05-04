"""Server-side message persistence helpers for the streaming chat agent.

Historically the streaming task (``stream_new_chat``/``stream_resume_chat``)
left ``new_chat_messages`` empty and relied on the frontend to round-trip
``POST /threads/{id}/messages`` afterwards. That gave authenticated clients
a "ghost-thread" abuse vector: skip the round-trip and burn LLM tokens
without leaving an audit trail. These helpers move both writes (the user
turn that triggered the stream and the assistant turn the stream produced)
into the server itself, idempotent against the partial unique index
``uq_new_chat_messages_thread_turn_role`` so legacy frontends that *do*
keep posting via ``appendMessage`` simply hit the unique-index recovery
path on the second writer instead of creating duplicates.

Assistant turn lifecycle
------------------------
The assistant side is split into two helpers so we can capture the row id
*before* the stream produces any output:

* ``persist_assistant_shell`` runs immediately after ``persist_user_turn``
  and INSERTs an empty assistant row anchored to ``(thread_id, turn_id,
  ASSISTANT)``. Returns the row id so the streaming layer can correlate
  later writes (token_usage, AgentActionLog future-correlation) against
  a stable PK from the start of the turn.
* ``finalize_assistant_turn`` runs from the streaming ``finally`` block.
  It UPDATEs the row's ``content`` to the rich ``ContentPart[]`` snapshot
  produced server-side by ``AssistantContentBuilder`` and writes the
  ``token_usage`` row using ``INSERT ... ON CONFLICT DO NOTHING`` against
  the ``uq_token_usage_message_id`` partial unique index from migration
  142, hard-eliminating any race against ``append_message``'s recovery
  branch.

Defensive contract
------------------

* Every helper runs inside ``shielded_async_session()`` so ``session.close()``
  survives starlette's mid-stream cancel scope on client disconnect.
* ``persist_user_turn`` and ``persist_assistant_shell`` use ``INSERT ... ON
  CONFLICT DO NOTHING ... RETURNING id`` keyed on the ``(thread_id, turn_id,
  role)`` partial unique index. On conflict the insert silently no-ops at
  the DB level — no Python ``IntegrityError`` is constructed, which
  eliminates spurious debugger pauses and keeps logs clean. On conflict a
  follow-up ``SELECT`` resolves the existing row id so the streaming layer
  can correlate writes against a stable PK.
* ``finalize_assistant_turn`` is best-effort: it never raises. The
  streaming ``finally`` block calls it from within
  ``anyio.CancelScope(shield=True)`` and any raised exception there
  would mask the real error.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.future import select

from app.db import (
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    TokenUsage,
    shielded_async_session,
)
from app.services.token_tracking_service import (
    TurnTokenAccumulator,
)
from app.utils.perf import get_perf_logger

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()


# Empty initial assistant content. ``finalize_assistant_turn`` overwrites
# this in a single UPDATE at end-of-stream with the full ``ContentPart[]``
# snapshot produced by ``AssistantContentBuilder``. We persist a one-element
# list with an empty text part so a crash between shell-INSERT and finalize
# leaves the row in a FE-renderable shape (blank bubble) instead of
# blowing up the history loader.
_EMPTY_SHELL_CONTENT: list[dict[str, Any]] = [{"type": "text", "text": ""}]

# Substituted content for genuinely empty turns (no text, no reasoning,
# no tool calls). The streaming layer flips to this when
# ``AssistantContentBuilder.is_empty()`` returns True so the persisted
# row is at least somewhat self-describing instead of an empty text
# bubble. The FE's ``ContentPart`` union doesn't include ``status``
# yet, so the history loader will silently drop this part and render
# a blank bubble (matches today's behaviour for empty turns); a follow-up
# FE PR adds the explicit "no response" rendering.
_STATUS_NO_RESPONSE: list[dict[str, Any]] = [
    {"type": "status", "text": "(no text response)"}
]


def _build_user_content(
    user_query: str,
    user_image_data_urls: list[str] | None,
    mentioned_documents: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build the persisted user-message ``content`` (assistant-ui v2 parts).

    Mirrors the shape the existing frontend posts via
    ``appendMessage`` (see ``surfsense_web/.../new-chat/[[...chat_id]]/page.tsx``):

        [{"type": "text", "text": "..."},
         {"type": "image", "image": "data:..."},
         {"type": "mentioned-documents", "documents": [{"id": int,
            "title": str, "document_type": str}, ...]}]

    The companion reader is
    ``app.utils.user_message_multimodal.split_persisted_user_content_parts``
    which expects exactly this shape — keep them in sync.

    ``mentioned_documents``: optional list of ``{id, title, document_type}``
    dicts. When non-empty (and a ``mentioned-documents`` part is not already
    in some other input shape), a single ``{"type": "mentioned-documents",
    "documents": [...]}`` part is appended. Mirrors the FE injection at
    ``page.tsx:281-286`` (``persistUserTurn``).
    """
    parts: list[dict[str, Any]] = [{"type": "text", "text": user_query or ""}]
    for url in user_image_data_urls or ():
        if isinstance(url, str) and url:
            parts.append({"type": "image", "image": url})
    if mentioned_documents:
        normalized: list[dict[str, Any]] = []
        for doc in mentioned_documents:
            if not isinstance(doc, dict):
                continue
            doc_id = doc.get("id")
            title = doc.get("title")
            document_type = doc.get("document_type")
            if doc_id is None or title is None or document_type is None:
                continue
            normalized.append(
                {
                    "id": doc_id,
                    "title": str(title),
                    "document_type": str(document_type),
                }
            )
        if normalized:
            parts.append({"type": "mentioned-documents", "documents": normalized})
    return parts


async def persist_user_turn(
    *,
    chat_id: int,
    user_id: str | None,
    turn_id: str,
    user_query: str,
    user_image_data_urls: list[str] | None = None,
    mentioned_documents: list[dict[str, Any]] | None = None,
) -> int | None:
    """Persist the user-side row for a chat turn and return its ``id``.

    Uses ``INSERT ... ON CONFLICT DO NOTHING ... RETURNING id`` keyed on the
    ``(thread_id, turn_id, role)`` partial unique index from migration 141
    (``WHERE turn_id IS NOT NULL``). On conflict the insert silently no-ops
    at the DB level — no Python ``IntegrityError`` is constructed, which
    eliminates the debugger pause that ``justMyCode=false`` + async greenlet
    interactions used to produce, and keeps production logs clean.

    Returns the ``id`` of the row that exists for this turn after the call:
    the freshly inserted ``id`` on the happy path, or the existing ``id``
    when a previous writer (legacy FE ``appendMessage`` racing the SSE
    stream, redelivered request, etc.) already wrote it. Returns ``None``
    only on genuine DB failure; the caller should yield a streaming error
    and abort the turn so we never produce a title/assistant row that
    isn't anchored to a persisted user message.

    Other constraint violations (FK, NOT NULL, etc.) still raise
    ``IntegrityError`` — only the ``(thread_id, turn_id, role)`` collision
    is silenced.
    """
    if not turn_id:
        # Defensive: turn_id is always populated by the streaming path
        # before this helper is called. If it isn't, we cannot be
        # idempotent against the unique index — refuse to write rather
        # than create a row the unique index can't dedupe.
        logger.error(
            "persist_user_turn called without a turn_id (chat_id=%s); skipping",
            chat_id,
        )
        return None

    t0 = time.perf_counter()
    outcome = "failed"
    resolved_id: int | None = None
    try:
        async with shielded_async_session() as ws:
            # Re-attach the thread row so we can also bump updated_at
            # in the same write — keeps the sidebar ordering accurate
            # when a user fires off a turn but never reaches the
            # legacy appendMessage.
            thread = await ws.get(NewChatThread, chat_id)
            author_uuid: UUID | None = None
            if user_id:
                try:
                    author_uuid = UUID(user_id)
                except (TypeError, ValueError):
                    logger.warning(
                        "persist_user_turn: invalid user_id=%r, persisting as anonymous",
                        user_id,
                    )

            content_payload = _build_user_content(
                user_query, user_image_data_urls, mentioned_documents
            )
            insert_stmt = (
                pg_insert(NewChatMessage)
                .values(
                    thread_id=chat_id,
                    role=NewChatMessageRole.USER,
                    content=content_payload,
                    author_id=author_uuid,
                    turn_id=turn_id,
                )
                .on_conflict_do_nothing(
                    index_elements=["thread_id", "turn_id", "role"],
                    index_where=sa_text("turn_id IS NOT NULL"),
                )
                .returning(NewChatMessage.id)
            )
            inserted_id = (await ws.execute(insert_stmt)).scalar()

            if inserted_id is None:
                # Conflict on partial unique index — another writer
                # (legacy FE appendMessage, redelivered request, etc.)
                # already persisted this row. Look it up and reuse.
                lookup = await ws.execute(
                    select(NewChatMessage.id).where(
                        NewChatMessage.thread_id == chat_id,
                        NewChatMessage.turn_id == turn_id,
                        NewChatMessage.role == NewChatMessageRole.USER,
                    )
                )
                existing_id = lookup.scalars().first()
                if existing_id is None:
                    # Conflict reported but no row found — extremely
                    # unlikely (concurrent DELETE). Surface as failure.
                    logger.warning(
                        "persist_user_turn: conflict but no matching row "
                        "(chat_id=%s, turn_id=%s)",
                        chat_id,
                        turn_id,
                    )
                    outcome = "integrity_no_match"
                    return None
                resolved_id = int(existing_id)
                outcome = "race_recovered"
            else:
                resolved_id = int(inserted_id)
                outcome = "inserted"
                # Bump thread.updated_at only on a real insert — when
                # we recovered an existing row the prior writer
                # already touched the thread.
                if thread is not None:
                    thread.updated_at = datetime.now(UTC)

            await ws.commit()
            return resolved_id
    except Exception:
        logger.exception(
            "persist_user_turn failed (chat_id=%s, turn_id=%s)",
            chat_id,
            turn_id,
        )
        return None
    finally:
        _perf_log.info(
            "[persist_user_turn] outcome=%s chat_id=%s turn_id=%s "
            "message_id=%s query_len=%d images=%d mentioned_docs=%d "
            "in %.3fs",
            outcome,
            chat_id,
            turn_id,
            resolved_id,
            len(user_query or ""),
            len(user_image_data_urls or ()),
            len(mentioned_documents or ()),
            time.perf_counter() - t0,
        )


async def persist_assistant_shell(
    *,
    chat_id: int,
    user_id: str | None,
    turn_id: str,
) -> int | None:
    """Pre-write an empty assistant row for the turn and return its id.

    Inserts a placeholder ``new_chat_messages`` row (empty text content) so
    the streaming layer has a stable ``message_id`` to correlate against
    for the rest of the turn. ``finalize_assistant_turn`` overwrites the
    ``content`` field at end-of-stream with the rich ``ContentPart[]``
    snapshot produced by ``AssistantContentBuilder``.

    Returns the row id on success, ``None`` on a genuine DB failure (caller
    should abort the turn rather than stream into a void).

    Idempotent against the ``(thread_id, turn_id, ASSISTANT)`` partial unique
    index from migration 141: if a row already exists (resume retry, racing
    legacy frontend, redelivered request, etc.) we look it up by
    ``(thread_id, turn_id, role)`` and return its existing id. The streaming
    layer is then free to UPDATE that row at finalize time.
    """
    if not turn_id:
        logger.error(
            "persist_assistant_shell called without a turn_id (chat_id=%s); skipping",
            chat_id,
        )
        return None

    t0 = time.perf_counter()
    outcome = "failed"
    resolved_id: int | None = None
    try:
        async with shielded_async_session() as ws:
            insert_stmt = (
                pg_insert(NewChatMessage)
                .values(
                    thread_id=chat_id,
                    role=NewChatMessageRole.ASSISTANT,
                    content=_EMPTY_SHELL_CONTENT,
                    author_id=None,
                    turn_id=turn_id,
                )
                .on_conflict_do_nothing(
                    index_elements=["thread_id", "turn_id", "role"],
                    index_where=sa_text("turn_id IS NOT NULL"),
                )
                .returning(NewChatMessage.id)
            )
            inserted_id = (await ws.execute(insert_stmt)).scalar()

            if inserted_id is None:
                # Conflict — another writer (legacy FE appendMessage,
                # resume retry, redelivered request) wrote the
                # (thread_id, turn_id, ASSISTANT) row first. Look it up
                # so the streaming layer can UPDATE the same row at
                # finalize time.
                lookup = await ws.execute(
                    select(NewChatMessage.id).where(
                        NewChatMessage.thread_id == chat_id,
                        NewChatMessage.turn_id == turn_id,
                        NewChatMessage.role == NewChatMessageRole.ASSISTANT,
                    )
                )
                existing_id = lookup.scalars().first()
                if existing_id is None:
                    logger.warning(
                        "persist_assistant_shell: conflict but no matching "
                        "(thread_id, turn_id, role) row found "
                        "(chat_id=%s, turn_id=%s)",
                        chat_id,
                        turn_id,
                    )
                    outcome = "integrity_no_match"
                    return None
                resolved_id = int(existing_id)
                outcome = "race_recovered"
            else:
                resolved_id = int(inserted_id)
                outcome = "inserted"

            await ws.commit()
            return resolved_id
    except Exception:
        logger.exception(
            "persist_assistant_shell failed (chat_id=%s, turn_id=%s)",
            chat_id,
            turn_id,
        )
        return None
    finally:
        _perf_log.info(
            "[persist_assistant_shell] outcome=%s chat_id=%s turn_id=%s "
            "message_id=%s in %.3fs",
            outcome,
            chat_id,
            turn_id,
            resolved_id,
            time.perf_counter() - t0,
        )


async def finalize_assistant_turn(
    *,
    message_id: int,
    chat_id: int,
    search_space_id: int,
    user_id: str | None,
    turn_id: str,
    content: list[dict[str, Any]],
    accumulator: TurnTokenAccumulator | None,
) -> None:
    """Finalize the assistant row and write its token_usage.

    Two writes in a single shielded session:

    1. ``UPDATE new_chat_messages SET content = :c, updated_at = now()
       WHERE id = :id`` — overwrites the placeholder ``persist_assistant_shell``
       wrote with the full ``ContentPart[]`` snapshot produced server-side.
    2. ``INSERT INTO token_usage (...) VALUES (...) ON CONFLICT (message_id)
       WHERE message_id IS NOT NULL DO NOTHING`` — uses the partial unique
       index ``uq_token_usage_message_id`` from migration 142 to make the
       insert idempotent against ``append_message``'s recovery branch
       (which uses the same ON CONFLICT clause).

    Substitutes the status-marker payload when ``content`` is empty
    (pure tool-call turn that aborted before any output, or interrupt
    before any event arrived). The status marker is preferable to a
    blank text bubble because token accounting still runs and an ops
    dashboard can flag the row.

    Best-effort — never raises. The streaming ``finally`` calls this
    from within ``anyio.CancelScope(shield=True)``; any raised exception
    here would mask the real error that triggered the cleanup.
    """
    if not turn_id:
        logger.error(
            "finalize_assistant_turn called without turn_id "
            "(chat_id=%s, message_id=%s); skipping",
            chat_id,
            message_id,
        )
        return
    if not message_id:
        logger.error(
            "finalize_assistant_turn called without message_id "
            "(chat_id=%s, turn_id=%s); skipping",
            chat_id,
            turn_id,
        )
        return

    payload: list[dict[str, Any]]
    is_status_marker = False
    if content:
        payload = content
    else:
        payload = _STATUS_NO_RESPONSE
        is_status_marker = True

    t0 = time.perf_counter()
    outcome = "failed"
    token_usage_attempted = bool(
        accumulator is not None and accumulator.calls and user_id
    )
    try:
        async with shielded_async_session() as ws:
            assistant_row = await ws.get(NewChatMessage, message_id)
            if assistant_row is None:
                logger.warning(
                    "finalize_assistant_turn: row not found "
                    "(chat_id=%s, message_id=%s, turn_id=%s); skipping",
                    chat_id,
                    message_id,
                    turn_id,
                )
                outcome = "row_missing"
                return

            assistant_row.content = payload
            assistant_row.updated_at = datetime.now(UTC)

            # Token usage. ``record_token_usage`` (used elsewhere) does
            # SELECT-then-INSERT in two statements which races with
            # ``append_message``. Switch to a single INSERT ... ON
            # CONFLICT DO NOTHING keyed on the migration-142 partial
            # unique index so the loser silently drops its write at
            # the DB level — exactly one row per ``message_id``,
            # regardless of which session committed first.
            if accumulator is not None and accumulator.calls and user_id:
                try:
                    user_uuid = UUID(user_id)
                except (TypeError, ValueError):
                    logger.warning(
                        "finalize_assistant_turn: invalid user_id=%r, "
                        "skipping token_usage row",
                        user_id,
                    )
                else:
                    insert_stmt = (
                        pg_insert(TokenUsage)
                        .values(
                            usage_type="chat",
                            prompt_tokens=accumulator.total_prompt_tokens,
                            completion_tokens=accumulator.total_completion_tokens,
                            total_tokens=accumulator.grand_total,
                            cost_micros=accumulator.total_cost_micros,
                            model_breakdown=accumulator.per_message_summary(),
                            call_details={"calls": accumulator.serialized_calls()},
                            thread_id=chat_id,
                            message_id=message_id,
                            search_space_id=search_space_id,
                            user_id=user_uuid,
                        )
                        .on_conflict_do_nothing(
                            index_elements=["message_id"],
                            index_where=sa_text("message_id IS NOT NULL"),
                        )
                    )
                    await ws.execute(insert_stmt)

            await ws.commit()
            outcome = "ok"
    except Exception:
        logger.exception(
            "finalize_assistant_turn failed (chat_id=%s, message_id=%s, turn_id=%s)",
            chat_id,
            message_id,
            turn_id,
        )
    finally:
        _perf_log.info(
            "[finalize_assistant_turn] outcome=%s chat_id=%s message_id=%s "
            "turn_id=%s parts=%d status_marker=%s "
            "token_usage_attempted=%s in %.3fs",
            outcome,
            chat_id,
            message_id,
            turn_id,
            len(payload),
            is_status_marker,
            token_usage_attempted,
            time.perf_counter() - t0,
        )
