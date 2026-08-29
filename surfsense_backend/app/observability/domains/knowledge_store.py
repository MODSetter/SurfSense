"""Knowledge-store telemetry: git-vs-Postgres writes, drift checks, git remotes."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.observability.signals import metrics as m
from app.observability.signals.tracing import span


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


@lru_cache(maxsize=1)
def _remote_connect():
    return m.get_meter().create_counter(
        "surfsense.knowledge_store.remote.connect",
        description="Count of workspace git-remote attach attempts per outcome.",
    )


@lru_cache(maxsize=1)
def _remote_push():
    return m.get_meter().create_counter(
        "surfsense.knowledge_store.remote.push",
        description="Count of workspace git-remote push attempts per outcome.",
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


def record_knowledge_store_remote_connect(*, provider: str, status: str) -> None:
    """Record one attach. ``status`` is ``connected`` or ``rejected``."""
    m.add(_remote_connect(), 1, {"remote.provider": provider, "status": status})


def record_knowledge_store_remote_push(
    *, status: str, provider: str | None = None
) -> None:
    """Record one push attempt. ``status`` is ``pushed``, ``noop``, or ``failed``."""
    m.add(_remote_push(), 1, {"remote.provider": provider or "none", "status": status})


def drift_sweep_span(*, extra: dict[str, Any] | None = None):
    """Parent span for one scheduled knowledge-store parity (drift) sweep."""
    return span("knowledge_store.drift.sweep", attributes=dict(extra or {}))


def drift_check_span(
    *,
    workspace_id: int,
    status: str,
    missing: int = 0,
    extra: int = 0,
    mismatched: int = 0,
):
    """Span for one workspace's parity check. The ``missing``/``extra``/
    ``mismatched`` path counts (named as in :class:`MigrationReport`) live in
    attributes, so a ``drift.status != ok`` alert opens a trace that already
    quantifies the git↔Postgres gap.
    """
    return span(
        "knowledge_store.drift.check",
        attributes={
            "workspace.id": int(workspace_id),
            "drift.status": status,
            "drift.missing": int(missing),
            "drift.extra": int(extra),
            "drift.mismatched": int(mismatched),
        },
    )


def remote_connect_span(*, workspace_id: int, provider: str):
    """Span around attaching one git remote to a workspace."""
    return span(
        "knowledge_store.remote.connect",
        attributes={"workspace.id": int(workspace_id), "remote.provider": provider},
    )


def remote_push_span(*, workspace_id: int, extra: dict[str, Any] | None = None):
    """Span around one worker attempt to fast-forward HEAD to the remote."""
    attrs: dict[str, Any] = {"workspace.id": int(workspace_id)}
    if extra:
        attrs.update(extra)
    return span("knowledge_store.remote.push", attributes=attrs)


def remote_sweep_span(*, extra: dict[str, Any] | None = None):
    """Parent span for one scheduled push of remotes whose stamp trails HEAD."""
    return span("knowledge_store.remote.sweep", attributes=dict(extra or {}))
