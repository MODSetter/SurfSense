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
def _remote_sync():
    return m.get_meter().create_counter(
        "surfsense.knowledge_store.remote.sync",
        description="Count of folder-sync ticks per outcome.",
    )


@lru_cache(maxsize=1)
def _remote_resolve():
    return m.get_meter().create_counter(
        "surfsense.knowledge_store.remote.resolve",
        description="Count of conflict/direction resolves per outcome.",
    )


@lru_cache(maxsize=1)
def _remote_disconnect():
    return m.get_meter().create_counter(
        "surfsense.knowledge_store.remote.disconnect",
        description="Count of git-remote disconnects.",
    )


@lru_cache(maxsize=1)
def _remote_enqueue():
    return m.get_meter().create_counter(
        "surfsense.knowledge_store.remote.enqueue",
        description="Count of folder-sync enqueue attempts (queued or dropped).",
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


def record_knowledge_store_remote_sync(
    *, status: str, provider: str | None = None, error_code: str | None = None
) -> None:
    """Record one sync tick.

    ``status`` is ``mirrored``, ``conflict``, ``worktree_busy``,
    ``blocked``, ``skipped``, or ``failed``.
    """
    attrs: dict[str, Any] = {
        "remote.provider": provider or "none",
        "status": status,
    }
    if error_code:
        attrs["error.code"] = error_code
    m.add(_remote_sync(), 1, attrs)


def record_knowledge_store_remote_resolve(
    *, direction: str, status: str, provider: str | None = None
) -> None:
    """Record one resolve. ``status`` is ``resolved`` or ``failed``."""
    m.add(
        _remote_resolve(),
        1,
        {
            "remote.provider": provider or "none",
            "remote.direction": direction,
            "status": status,
        },
    )


def record_knowledge_store_remote_disconnect(*, provider: str | None = None) -> None:
    m.add(_remote_disconnect(), 1, {"remote.provider": provider or "none"})


def record_knowledge_store_remote_enqueue(*, status: str) -> None:
    """Record one enqueue attempt. ``status`` is ``queued`` or ``failed``."""
    m.add(_remote_enqueue(), 1, {"status": status})


def record_knowledge_store_remote_push(
    *, status: str, provider: str | None = None
) -> None:
    """Backward-compatible alias of :func:`record_knowledge_store_remote_sync`."""
    record_knowledge_store_remote_sync(status=status, provider=provider)


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


def remote_connect_span(
    *, workspace_id: int, provider: str, extra: dict[str, Any] | None = None
):
    """Span around attaching one git remote to a workspace."""
    attrs: dict[str, Any] = {
        "workspace.id": int(workspace_id),
        "remote.provider": provider,
    }
    if extra:
        attrs.update(extra)
    return span("knowledge_store.remote.connect", attributes=attrs)


def remote_sync_span(*, workspace_id: int, extra: dict[str, Any] | None = None):
    """Span around one folder-sync tick (clone, plan, apply, pathspec-push)."""
    attrs: dict[str, Any] = {"workspace.id": int(workspace_id)}
    if extra:
        attrs.update(extra)
    return span("knowledge_store.remote.sync", attributes=attrs)


def remote_resolve_span(
    *, workspace_id: int, direction: str, extra: dict[str, Any] | None = None
):
    """Span around overwriting one side of the bijection."""
    attrs: dict[str, Any] = {
        "workspace.id": int(workspace_id),
        "remote.direction": direction,
    }
    if extra:
        attrs.update(extra)
    return span("knowledge_store.remote.resolve", attributes=attrs)


def remote_disconnect_span(*, workspace_id: int):
    """Span around dropping the connected remote and its shadow clone."""
    return span(
        "knowledge_store.remote.disconnect",
        attributes={"workspace.id": int(workspace_id)},
    )


def remote_shadow_span(*, workspace_id: int, operation: str):
    """Span around clone/refresh/push of their forge checkout."""
    return span(
        "knowledge_store.remote.shadow",
        attributes={
            "workspace.id": int(workspace_id),
            "shadow.operation": operation,
        },
    )


def remote_push_span(*, workspace_id: int, extra: dict[str, Any] | None = None):
    """Backward-compatible alias of :func:`remote_sync_span`."""
    return remote_sync_span(workspace_id=workspace_id, extra=extra)
