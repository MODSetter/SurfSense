"""Celery task detecting — and repairing — Postgres↔git drift on flipped workspaces.

The always-on version of the fleet runner's dry run: for every workspace with
``knowledge_store_enabled``, compare the store's head against Postgres by
content address and emit one ``knowledge_store.drift.check`` data point.
An alert on ``status != ok`` replaces reading JSONL reports by hand.

The hourly sweep converges the drift it can see, which is only git running
ahead of the stamp; drift on the Postgres side is invisible to it, because both
sides of its comparison are git revisions. This check sees that drift, so it
also closes it — leaving the fix as a runbook step would make repair depend on
someone noticing the alert.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.celery_app import celery_app
from app.knowledge_store.migrate import MigrationReport, migrate_workspace
from app.knowledge_store.settings import load_knowledge_store_settings
from app.observability import metrics, otel
from app.tasks.celery_tasks.knowledge_store.index_tasks import reindex_knowledge_store

logger = logging.getLogger(__name__)

#: Repairs enqueued per run. Drift should be rare, so a run wanting more than a
#: handful is a systemic problem, and fanning out whole-tree converges would
#: compound it rather than fix it; the rest wait for the next run.
#:
#: ponytail: drift ``index_tree`` cannot fix — a Postgres row carrying no path
#: marker and having no file in the tree, i.e. some writer bypassing git — costs
#: one rebuild per run until a human intervenes. The alarm persists throughout,
#: so it stays visible; the upgrade path is a per-workspace attempt count to
#: back off after a repair that changed nothing.
REPAIR_ENQUEUE_CAP = 10


@celery_app.task(name="check_knowledge_store_drift")
def check_knowledge_store_drift() -> dict[str, int]:
    """Return status counts, e.g. ``{"ok": 12, "drift": 1}``."""
    if not load_knowledge_store_settings().enabled:
        return {}
    return asyncio.run(_check_flipped_workspaces())


async def _check_flipped_workspaces() -> dict[str, int]:
    from app.db import Workspace, async_session_maker

    async with async_session_maker() as session:
        workspace_ids = (
            (
                await session.execute(
                    select(Workspace.id).where(
                        Workspace.knowledge_store_enabled.is_(True)
                    )
                )
            )
            .scalars()
            .all()
        )

    counts: dict[str, int] = {}
    repairs = 0
    with otel.drift_sweep_span() as sweep:
        for workspace_id in workspace_ids:
            # Fresh session per workspace, like the fleet runner: one workspace's
            # failure must not poison the next check.
            async with async_session_maker() as session:
                report = await migrate_workspace(session, workspace_id, dry_run=True)
            status = _status(report)
            counts[status] = counts.get(status, 0) + 1
            with otel.drift_check_span(
                workspace_id=workspace_id,
                status=status,
                missing=len(report.missing),
                extra=len(report.extra),
                mismatched=len(report.mismatched),
            ):
                metrics.record_knowledge_store_drift_check(
                    workspace_id=workspace_id, status=status
                )
            if status != "ok":
                logger.warning(
                    "Knowledge store drift check for workspace %s: %s "
                    "(missing=%d extra=%d mismatched=%d error=%s)",
                    workspace_id,
                    status,
                    len(report.missing),
                    len(report.extra),
                    len(report.mismatched),
                    report.error,
                )
            if status == "drift" and repairs < REPAIR_ENQUEUE_CAP:
                # git is the truth, so the whole-tree converge is the repair: it
                # upserts rows for paths Postgres lacks, overwrites content that
                # disagrees, and prunes marked rows whose file is gone. `error`
                # is deliberately excluded — a store the check could not read
                # will not be fixed by indexing it harder.
                reindex_knowledge_store.delay(workspace_id)
                repairs += 1
        sweep.set_attributes(
            {
                "drift.workspaces": len(workspace_ids),
                "drift.ok": counts.get("ok", 0),
                "drift.drift": counts.get("drift", 0),
                "drift.error": counts.get("error", 0),
                "drift.repairs_enqueued": repairs,
            }
        )
    return counts


def _status(report: MigrationReport) -> str:
    if report.error:
        return "error"
    return "ok" if report.ok else "drift"
