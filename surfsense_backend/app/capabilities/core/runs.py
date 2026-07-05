"""Shared run recorder: persist one ``runs`` row per capability invocation.

Both doors (the agent tool adapter and the REST endpoint) call :func:`record_run`
so agent and API runs land identically. Output is serialized to JSONL (one item
per line, ``exclude_none``) so the ``read_run``/``search_run`` tools can page and
grep by line. Recording is best-effort: a failure here never fails an otherwise
successful scrape — the caller degrades gracefully on a ``None`` return.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from sqlalchemy import text

from app.db import Run, ToolOutputSpill

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

RUN_OUTPUT_CHAR_CAP = 40_000
"""~10k tokens. Capability outputs at/under this are returned inline; larger ones
are stored and previewed. Read-tool responses pass through the same cap."""

RUNS_RETENTION_DAYS = 30
SPILLS_RETENTION_DAYS = 7
_CLEANUP_BATCH = 200
_CLEANUP_SAMPLE_RATE = 0.01
"""ponytail: opportunistic bounded cleanup fired on ~1% of inserts. A dedicated
cron/scheduler is the upgrade path if row volume ever outpaces this."""


@dataclass(frozen=True)
class SerializedOutput:
    """A capability output flattened to JSONL, computed once and reused."""

    text: str
    item_count: int
    char_count: int


def serialize_output(output: BaseModel) -> SerializedOutput:
    """Flatten a capability output to JSONL (one item per line, ``exclude_none``).

    Capability outputs wrap their results in an ``items`` list; each item becomes
    one JSON line so line-based paging/grep works. A non-``items`` output is dumped
    as a single line.
    """
    items = getattr(output, "items", None)
    if isinstance(items, list):
        lines = [
            json.dumps(_dump(item), default=str, ensure_ascii=False) for item in items
        ]
    else:
        lines = [
            json.dumps(
                output.model_dump(exclude_none=True), default=str, ensure_ascii=False
            )
        ]

    body = "\n".join(lines)
    return SerializedOutput(text=body, item_count=len(lines), char_count=len(body))


def _dump(item: Any) -> Any:
    if isinstance(item, BaseModel):
        return item.model_dump(exclude_none=True)
    return item


async def record_run(
    session: AsyncSession,
    *,
    workspace_id: int,
    capability: str,
    origin: str,
    status: str,
    serialized: SerializedOutput | None = None,
    input: dict | None = None,
    user_id: Any | None = None,
    thread_id: str | None = None,
    error: str | None = None,
    duration_ms: int | None = None,
    cost_micros: int | None = None,
) -> str | None:
    """Persist a run row and return its id, or ``None`` on failure (best-effort).

    Both doors pass a dedicated session (from ``async_session_maker``), so this
    function owns the commit — recording never entangles the request transaction
    and survives an executor error that leaves the request session unusable.
    """
    try:
        run = Run(
            workspace_id=workspace_id,
            user_id=user_id,
            thread_id=thread_id,
            capability=capability,
            origin=origin,
            status=status,
            error=error,
            input=input,
            output_text=serialized.text if serialized else None,
            item_count=serialized.item_count if serialized else 0,
            char_count=serialized.char_count if serialized else 0,
            duration_ms=duration_ms,
            cost_micros=cost_micros,
        )
        session.add(run)
        await session.flush()
        run_id = str(run.id)
        await _maybe_cleanup(session, "runs", RUNS_RETENTION_DAYS)
        await session.commit()
        return run_id
    except Exception:
        logger.exception("record_run failed for capability=%s", capability)
        try:
            await session.rollback()
        except Exception:
            logger.exception("record_run rollback failed")
        return None


async def record_spill(
    session: AsyncSession,
    *,
    content: str,
    spill_id: Any | None = None,
    workspace_id: int | None = None,
    thread_id: str | None = None,
    tool_name: str | None = None,
) -> str | None:
    """Persist a context-editing spill row and return its id, or ``None``.

    ``spill_id`` may be supplied so the caller's placeholder can reference the id
    before the row is flushed (the context-editing middleware needs this). The
    write is idempotent on that id: context edits re-apply on every model call
    (they operate on a per-call copy of the messages), so the same spill arrives
    repeatedly — an existing row is left as-is and its id returned.
    """
    try:
        kwargs: dict[str, Any] = {}
        if spill_id is not None:
            kwargs["id"] = spill_id
            existing = await session.get(ToolOutputSpill, spill_id)
            if existing is not None:
                return str(spill_id)
        spill = ToolOutputSpill(
            workspace_id=workspace_id,
            thread_id=thread_id,
            tool_name=tool_name,
            content=content,
            char_count=len(content),
            **kwargs,
        )
        session.add(spill)
        await session.flush()
        spill_id = str(spill.id)
        await _maybe_cleanup(session, "tool_output_spills", SPILLS_RETENTION_DAYS)
        await session.commit()
        return spill_id
    except Exception:
        logger.exception("record_spill failed")
        try:
            await session.rollback()
        except Exception:
            logger.exception("record_spill rollback failed")
        return None


async def _maybe_cleanup(session: AsyncSession, table: str, retention_days: int) -> None:
    """Delete a bounded batch of expired rows on ~1% of inserts."""
    if random.random() >= _CLEANUP_SAMPLE_RATE:
        return
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    # ponytail: LIMIT-bounded so a long backlog never lands as one giant delete.
    # `table` is one of two hardcoded literals below — never user input.
    await session.execute(
        text(
            f"DELETE FROM {table} WHERE id IN "
            f"(SELECT id FROM {table} WHERE created_at < :cutoff LIMIT :batch)"
        ),
        {"cutoff": cutoff, "batch": _CLEANUP_BATCH},
    )
