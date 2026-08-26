"""Knowledge-store telemetry: git-vs-Postgres write outcomes and drift checks."""

from __future__ import annotations

from functools import lru_cache

from app.observability.signals import metrics as m


@lru_cache(maxsize=1)
def _record_outcome():
    return m.get_meter().create_counter(
        "surfsense.knowledge_store.record.outcome",
        description="Count of knowledge-store recording outcomes per write flow.",
    )


@lru_cache(maxsize=1)
def _drift_checks():
    return m.get_meter().create_counter(
        "surfsense.knowledge_store.drift.check",
        description="Count of scheduled knowledge-store parity checks per outcome.",
    )


def record_knowledge_store_record_outcome(
    *, flow: str, status: str, error_category: str | None = None
) -> None:
    """Record one write attempt. ``flow`` = write path (``editor_save`` /
    ``sync_batch`` / ``turn_commit`` / ``delete`` / ``move``); ``status`` =
    ``recorded`` / ``noop`` / ``failed`` (``failed`` means git drifts behind PG).
    """
    m.add(
        _record_outcome(),
        1,
        m.attrs_with_error_category({"flow": flow, "status": status}, error_category),
    )


def record_knowledge_store_drift_check(*, workspace_id: int, status: str) -> None:
    """Record one parity check. ``status`` is ``ok``, ``drift``, or ``error``."""
    m.add(_drift_checks(), 1, {"workspace.id": workspace_id, "status": status})
