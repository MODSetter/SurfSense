"""Shared finally-block helpers: session close, GC pass, native-heap trim.

These are called from inside an ``anyio.CancelScope(shield=True)`` block in
each flow's ``finally`` (Starlette's BaseHTTPMiddleware cancels the scope on
client disconnect; without the shield the very first ``await`` would raise
``CancelledError`` and the rest of cleanup — including ``session.close()`` —
would never run).
"""

from __future__ import annotations

import contextlib
import gc
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import shielded_async_session
from app.services.chat_session_state_service import clear_ai_responding
from app.utils.perf import get_perf_logger, log_system_snapshot, trim_native_heap

_perf_log = get_perf_logger()
logger = logging.getLogger(__name__)


async def close_session_and_clear_ai_responding(
    session: AsyncSession, chat_id: int
) -> None:
    """Rollback + clear AI-responding flag + expunge_all + close.

    On rollback failure we fall back to a fresh shielded session for the flag
    clear so a UI is never stuck on "AI is responding…" after a crash.
    """
    try:
        await session.rollback()
        await clear_ai_responding(session, chat_id)
    except Exception:
        try:
            async with shielded_async_session() as fresh_session:
                await clear_ai_responding(fresh_session, chat_id)
        except Exception:
            logger.warning(
                "Failed to clear AI responding state for thread %s", chat_id
            )

    with contextlib.suppress(Exception):
        session.expunge_all()

    with contextlib.suppress(Exception):
        await session.close()


def run_gc_pass(*, log_prefix: str, chat_id: int) -> None:
    """One full gen0/1/2 pass + native-heap trim + END system snapshot.

    Breaking circular refs held by the agent graph, tools, and LLM wrappers
    needs to happen in the caller (set the locals to ``None``) — this just
    runs the collector and logs how many objects came back.
    """
    collected = gc.collect(0) + gc.collect(1) + gc.collect(2)
    if collected:
        _perf_log.info(
            "[%s] gc.collect() reclaimed %d objects (chat_id=%s)",
            log_prefix,
            collected,
            chat_id,
        )
    trim_native_heap()
    log_system_snapshot(f"{log_prefix}_END")
