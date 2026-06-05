"""Shared poll-until-terminal helper for Celery-backed deliverables.

Lives in ``app.agents.shared`` (neutral kernel package, no dependency on
``multi_agent_chat``) so both the shared tools under ``app/agents/shared/tools/``
and the multi-agent subagent tools under
``app/agents/multi_agent_chat/subagents/builtins/deliverables/tools/`` can import
it without creating a circular dependency.

Background
----------
Tools like ``generate_podcast`` and ``generate_video_presentation`` enqueue
the heavy work to Celery and historically returned immediately with a
"pending" status. That works for very-long deliverables but hurts UX for
the common case (most podcasts finish in 10-30 seconds): the agent sends
a "kicked off, check back in a minute" reply *before* the worker is done,
so the user never gets a "ready" confirmation.

This helper bridges that gap. The tool dispatches the Celery task as
before, then polls the artefact row's ``status`` column **until it
reaches a terminal value** (READY / FAILED). The tool then returns a
real terminal outcome — never a pending one.

No wall-clock budget here on purpose
------------------------------------
Layering a second budget on top of the existing per-invocation safety
nets just confused the UX. The real ceilings are:

* **Multi-agent mode** — ``SURFSENSE_SUBAGENT_INVOKE_TIMEOUT_SECONDS``
  (default ``300.0``, ``0`` to disable) caps how long any single
  ``task(subagent, ...)`` invocation can run. If a deliverable needs
  longer than this, the subagent invocation is cancelled and the
  orchestrator surfaces a "subagent timed out" ToolMessage. Operators
  who routinely generate long videos should raise that ceiling (or set
  it to ``0`` for true unbounded waits).
* **Single-agent mode** — the chat's HTTP stream / process lifetime is
  the only ceiling. Truly indefinite waits work here, but a dead Celery
  worker will leave the row in PENDING/GENERATING forever; treat that
  as an operational concern, not a UX concern.

Configuration
-------------
None. The poll cadence is hardcoded at 1.5s — small enough to feel
responsive (~6 polls per typical 10s podcast), large enough to avoid
hammering the DB under burst traffic. Override at the call site if a
specific tool needs a different cadence.
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute

from app.db import shielded_async_session

logger = logging.getLogger(__name__)


_DEFAULT_POLL_INTERVAL_SECONDS: float = 1.5


async def wait_for_deliverable(
    *,
    model: type,
    row_id: int,
    columns: list[InstrumentedAttribute[Any]],
    terminal_statuses: set[Enum],
    poll_interval_s: float = _DEFAULT_POLL_INTERVAL_SECONDS,
) -> tuple[Enum, tuple[Any, ...], float]:
    """Poll ``model`` row ``row_id`` until ``columns[0]`` reaches a terminal status.

    Blocks until the row's status column matches one of
    ``terminal_statuses``. There is no internal wall-clock budget; cancel
    from the outside (subagent timeout, HTTP disconnect, task
    cancellation) if you need a ceiling. See module docstring.

    The first entry of ``columns`` must be the status column; additional
    columns (e.g. ``Podcast.file_location``) are returned alongside the
    final status so callers can build their payload without a second
    roundtrip.

    A fresh ``shielded_async_session`` is opened per poll so we never
    hold a transaction across the wait, and a failed poll is logged but
    does not abort the wait — transient DB hiccups should not collapse
    the tool call.

    Returns
    -------
    ``(terminal_status, columns, elapsed_seconds)``
        ``columns`` mirrors the requested ``columns`` (including the
        status itself in position 0).
    """
    if not columns:
        raise ValueError("wait_for_deliverable requires at least the status column")

    start = time.monotonic()

    while True:
        await asyncio.sleep(poll_interval_s)
        row: tuple[Any, ...] | None = None
        try:
            async with shielded_async_session() as session:
                result = await session.execute(
                    select(*columns).where(model.id == row_id)
                )
                row = result.first()
        except Exception as exc:
            logger.warning(
                "[deliverable_wait] poll failed model=%s id=%s err=%r",
                getattr(model, "__name__", str(model)),
                row_id,
                exc,
            )

        if row is not None:
            status_val = row[0]
            if status_val in terminal_statuses:
                return status_val, tuple(row), time.monotonic() - start
