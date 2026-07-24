"""Live progress plumbing shared by every capability run.

A single module-level :func:`emit_progress` lets the proprietary scraper code
report what it is doing without knowing *who* is listening. The active listener
is held in a :class:`contextvars.ContextVar`, so:

* the REST async door sets a reporter bound to the run's bus channel — every
  event is streamed live over SSE and coarse ones are buffered for persistence;
* the REST sync door and the agent door set a buffer-only reporter — coarse
  events still land in ``runs.progress`` and (in a chat/graph context) surface
  as ``scraper_progress`` custom events on the active thinking step;
* outside any run (unit tests calling a scraper directly) the var is unset and
  :func:`emit_progress` is a **no-op**, so scraper code can call it freely.

The event shape is one flexible dict, not a class hierarchy::

    {"type": "run.progress", "ts": <epoch ms>, "phase": str,
     "message"?: str, "current"?: int, "total"?: int, "unit"?: str,
     "detail"?: {...}}
"""

from __future__ import annotations

import contextlib
import logging
import time
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    from app.capabilities.core.events import RunEventBus

logger = logging.getLogger(__name__)

# Coarse counters are persisted/chat-surfaced at most once per this window per
# (phase, unit) key; the raw fine-grained stream is unthrottled on the bus.
_COUNTER_THROTTLE_MS = 1000
# ponytail: bound the persisted coarse log so a runaway scrape can't write an
# unbounded JSONB blob. Upgrade path: page the log into its own table.
_MAX_COARSE_EVENTS = 1000


class ProgressReporter:
    """Sink for one run's progress events.

    Publishes every event to the bus (live SSE tail) and keeps a throttled,
    bounded list of *coarse* events for persistence + chat surfacing.
    """

    def __init__(
        self, *, run_id: str | None = None, bus: RunEventBus | None = None
    ) -> None:
        self.run_id = run_id
        self.bus = bus
        self.coarse: list[dict[str, Any]] = []
        self._last_phase: str | None = None
        self._last_counter_ts: dict[tuple[str, str | None], int] = {}

    def handle(self, event: dict[str, Any]) -> None:
        # Live tail: every event, unthrottled (this is the "stream everything").
        if self.bus is not None and self.run_id is not None:
            self.bus.publish(self.run_id, event)

        if not self._is_coarse(event):
            return

        if len(self.coarse) < _MAX_COARSE_EVENTS:
            self.coarse.append(event)
        # Chat surface: coarse events become thinking-step items when a LangGraph
        # run context is active (agent door). No-op elsewhere.
        _dispatch_chat_event(event)

    def _is_coarse(self, event: dict[str, Any]) -> bool:
        phase = event.get("phase", "")
        if phase != self._last_phase:
            self._last_phase = phase
            self._last_counter_ts.clear()
            return True
        if "current" not in event:
            return True
        key = (phase, event.get("unit"))
        now = int(event.get("ts", 0))
        last = self._last_counter_ts.get(key, 0)
        if now - last >= _COUNTER_THROTTLE_MS:
            self._last_counter_ts[key] = now
            return True
        return False


_active_reporter: ContextVar[ProgressReporter | None] = ContextVar(
    "active_progress_reporter", default=None
)


def emit_progress(
    phase: str,
    message: str | None = None,
    *,
    current: int | None = None,
    total: int | None = None,
    unit: str | None = None,
    **detail: Any,
) -> None:
    """Report a progress event for the active run; a no-op when none is active.

    Safe to call from anywhere in the scraper code path — never raises into the
    caller.
    """
    reporter = _active_reporter.get()
    if reporter is None:
        return
    try:
        event: dict[str, Any] = {
            "type": "run.progress",
            "ts": int(time.time() * 1000),
            "phase": phase,
        }
        if message is not None:
            event["message"] = message
        if current is not None:
            event["current"] = current
        if total is not None:
            event["total"] = total
        if unit is not None:
            event["unit"] = unit
        if detail:
            event["detail"] = detail
        reporter.handle(event)
    except Exception:  # pragma: no cover - progress must never break a scrape
        logger.debug("emit_progress failed; suppressed", exc_info=True)


@contextlib.contextmanager
def progress_scope(
    *, run_id: str | None = None, bus: RunEventBus | None = None
) -> Iterator[ProgressReporter]:
    """Bind a :class:`ProgressReporter` for the duration of a run.

    The contextvar set here propagates to every coroutine awaited inside the
    ``with`` block (same task), so deep scraper code sees it without wiring.
    """
    reporter = ProgressReporter(run_id=run_id, bus=bus)
    token = _active_reporter.set(reporter)
    try:
        yield reporter
    finally:
        _active_reporter.reset(token)


def _dispatch_chat_event(event: dict[str, Any]) -> None:
    """Best-effort forward to the chat SSE relay via a LangGraph custom event.

    Only meaningful inside an agent tool call (there is a run context); raises
    otherwise, which we swallow — mirrors ``retry_after``'s guarded dispatch.
    """
    try:
        from langchain_core.callbacks import dispatch_custom_event

        dispatch_custom_event("scraper_progress", event)
    except Exception:
        logger.debug("scraper_progress dispatch skipped (no run context)")
