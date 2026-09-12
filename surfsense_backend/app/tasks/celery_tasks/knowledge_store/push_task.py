"""Push HEAD to the workspace git remote after a durable store revision."""

from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.exceptions import GitPushError
from app.knowledge_store.settings import (
    knowledge_store_enabled_for,
    load_knowledge_store_settings,
)
from app.observability.domains import knowledge_store
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task
from app.tasks.celery_tasks.knowledge_store.index_tasks import (
    LOCK_RETRY_DELAY_SECONDS,
    LOCK_RETRY_LIMIT,
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


async def _push(workspace_id: int) -> str | None:
    if not await knowledge_store_enabled_for(workspace_id):
        with knowledge_store.remote_sync_span(workspace_id=workspace_id) as sp:
            _observe_skip(sp, workspace_id, reason="not_git_native")
        return None
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        store = KnowledgeStore.for_workspace(workspace_id).with_session(session)
        remotes = await store.remotes.list()
        if not remotes:
            with knowledge_store.remote_sync_span(workspace_id=workspace_id) as sp:
                _observe_skip(sp, workspace_id, reason="no_remote")
            return None
        try:
            sha = await store.remotes.sync()
        except Exception as exc:
            await store.remotes.record_push_failure(str(exc))
            await session.commit()
            return None
        if sha is not None:
            await store.remotes.record_push(sha)
        await session.commit()
        return sha


def _observe_skip(sp, workspace_id: int, *, reason: str) -> None:
    sp.set_attribute("sync.status", "skipped")
    sp.set_attribute("sync.error_code", reason)
    knowledge_store.record_knowledge_store_remote_sync(
        status="skipped", error_code=reason
    )
    logger.info(
        "Knowledge store remote sync workspace=%s status=skipped reason=%s",
        workspace_id,
        reason,
    )
