"""Push HEAD to the workspace git remote after a durable store revision."""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.celery_app import celery_app
from app.db import Workspace
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.exceptions import GitPushError
from app.knowledge_store.remote.persistence.models import WorkspaceGitRemotes
from app.knowledge_store.settings import (
    knowledge_store_enabled_for,
    load_knowledge_store_settings,
)
from app.observability import metrics, otel
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task
from app.tasks.celery_tasks.knowledge_store.index_tasks import (
    LOCK_RETRY_DELAY_SECONDS,
    LOCK_RETRY_LIMIT,
    SWEEP_ENQUEUE_CAP,
)

logger = logging.getLogger(__name__)


@celery_app.task(
    name="push_knowledge_store_revision", bind=True, max_retries=LOCK_RETRY_LIMIT
)
def push_knowledge_store_revision(self, workspace_id: int) -> str | None:
    """Fast-forward HEAD to the attached remote. No-op if none or already pushed."""
    if not load_knowledge_store_settings().enabled:
        return None
    try:
        return run_async_celery_task(lambda: _push(workspace_id))
    except GitPushError:
        return None
    except Exception as exc:
        raise self.retry(countdown=LOCK_RETRY_DELAY_SECONDS, exc=exc) from exc


@celery_app.task(name="push_lagging_workspace_remotes")
def push_lagging_workspace_remotes() -> int:
    """Enqueue push where a remote's stamp trails the store HEAD."""
    if not load_knowledge_store_settings().enabled:
        return 0
    return run_async_celery_task(_sweep)


async def _push(workspace_id: int) -> str | None:
    with otel.remote_push_span(workspace_id=workspace_id) as sp:
        return await _push_head(workspace_id, sp)


async def _push_head(workspace_id: int, sp) -> str | None:
    if not await knowledge_store_enabled_for(workspace_id):
        _observe_push(
            sp, workspace_id, status="noop", reason="not_git_native"
        )
        return None
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        store = KnowledgeStore.for_workspace(workspace_id).with_session(session)
        remotes = await store.remotes.list()
        if not remotes:
            _observe_push(sp, workspace_id, status="noop", reason="no_remote")
            return None
        target = remotes[0]
        head = await store.head()
        if head is None or head == target.last_pushed_revision:
            _observe_push(
                sp,
                workspace_id,
                status="noop",
                reason="already_pushed",
                provider=target.provider,
            )
            return None
        try:
            with otel.span("knowledge_store.remote.credentials"):
                creds = await store.remotes.credentials()
            sha = await store.push(
                url=target.url,
                ref=f"refs/heads/{target.branch}",
                username=creds.username,
                password=creds.password,
            )
        except GitPushError as exc:
            _observe_push(
                sp,
                workspace_id,
                status="failed",
                reason=_push_reason(exc),
                provider=target.provider,
            )
            await store.remotes.record_push_failure(str(exc))
            await session.commit()
            return None
        sp.set_attribute("git.revision", sha)
        _observe_push(
            sp,
            workspace_id,
            status="pushed",
            reason="head",
            provider=target.provider,
        )
        await store.remotes.record_push(sha)
        await session.commit()
        return sha


def _observe_push(
    sp,
    workspace_id: int,
    *,
    status: str,
    reason: str,
    provider: str | None = None,
) -> None:
    sp.set_attribute("push.status", status)
    sp.set_attribute("push.reason", reason)
    if provider:
        sp.set_attribute("remote.provider", provider)
    metrics.record_knowledge_store_remote_push(status=status, provider=provider)
    logger.info(
        "Knowledge store remote push workspace=%s status=%s reason=%s provider=%s",
        workspace_id,
        status,
        reason,
        provider or "none",
    )


def _push_reason(exc: GitPushError) -> str:
    if exc.message == "non-fast-forward":
        return "non_fast_forward"
    if exc.message == "nothing to push":
        return "empty"
    return "send_pack"


async def _sweep() -> int:
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(
                WorkspaceGitRemotes.workspace_id,
                WorkspaceGitRemotes.last_pushed_revision,
            )
            .join(Workspace, Workspace.id == WorkspaceGitRemotes.workspace_id)
            .where(Workspace.knowledge_store_enabled.is_(True))
        )
        stamps = dict(result.all())

    enqueued = 0
    with otel.remote_sweep_span() as sweep:
        for workspace_id, stamp in stamps.items():
            if enqueued >= SWEEP_ENQUEUE_CAP:
                break
            head = await KnowledgeStore.for_workspace(workspace_id).head()
            if head is None or head == stamp:
                continue
            push_knowledge_store_revision.delay(workspace_id)
            enqueued += 1
        sweep.set_attributes(
            {
                "remote.candidates": len(stamps),
                "remote.enqueued": enqueued,
            }
        )
    if enqueued:
        logger.info(
            "Remote push sweep enqueued %d workspaces from %d candidates",
            enqueued,
            len(stamps),
        )
    return enqueued
