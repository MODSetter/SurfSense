"""Celery task detecting Postgres↔git drift on flipped workspaces.

The always-on version of the fleet runner's dry run: for every workspace with
``knowledge_store_enabled``, compare the store's head against Postgres by
content address and emit one ``knowledge_store.drift.check`` data point.
An alert on ``status != ok`` replaces reading JSONL reports by hand.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.celery_app import celery_app
from app.knowledge_store.migrate import MigrationReport, migrate_workspace
from app.knowledge_store.settings import load_knowledge_store_settings
from app.observability import metrics

logger = logging.getLogger(__name__)


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
    for workspace_id in workspace_ids:
        # Fresh session per workspace, like the fleet runner: one workspace's
        # failure must not poison the next check.
        async with async_session_maker() as session:
            report = await migrate_workspace(session, workspace_id, dry_run=True)
        status = _status(report)
        counts[status] = counts.get(status, 0) + 1
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
    return counts


def _status(report: MigrationReport) -> str:
    if report.error:
        return "error"
    return "ok" if report.ok else "drift"
