"""A workspace's git remotes. v1: at most one destination."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.forges import provider_for
from app.knowledge_store.remote.persistence import WorkspaceRemoteRepository
from app.knowledge_store.remote.queue import enqueue_push
from app.knowledge_store.remote.schemas import (
    RemoteCredentials,
    RemoteSpec,
    RemoteStatus,
)
from app.knowledge_store.settings import knowledge_store_enabled_for
from app.observability import metrics, otel

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.knowledge_store.engines.git import GitContentEngine


class WorkspaceRemotes:
    """Git remotes attached to this workspace."""

    def __init__(
        self,
        workspace_id: int | str,
        engine: GitContentEngine,
        session: AsyncSession,
    ) -> None:
        self._workspace_id = int(workspace_id)
        self._engine = engine
        self._session = session
        self._rows = WorkspaceRemoteRepository(session)

    async def list(self) -> list[RemoteStatus]:
        return await self._rows.list_statuses(self._workspace_id)

    async def add(self, spec: RemoteSpec) -> RemoteStatus:
        with otel.remote_connect_span(
            workspace_id=self._workspace_id, provider=spec.provider
        ) as sp:
            try:
                status = await self._add(spec)
            except RemoteError as exc:
                sp.set_attribute("connect.status", "rejected")
                sp.set_attribute("connect.code", exc.code)
                metrics.record_knowledge_store_remote_connect(
                    provider=spec.provider, status="rejected"
                )
                logger.info(
                    "Git remote rejected workspace=%s provider=%s code=%s",
                    self._workspace_id,
                    spec.provider,
                    exc.code,
                )
                raise
            sp.set_attribute("connect.status", "connected")
            metrics.record_knowledge_store_remote_connect(
                provider=spec.provider, status="connected"
            )
            logger.info(
                "Git remote connected workspace=%s provider=%s",
                self._workspace_id,
                spec.provider,
            )
            return status

    async def _add(self, spec: RemoteSpec) -> RemoteStatus:
        if not await knowledge_store_enabled_for(self._workspace_id):
            raise RemoteError("not_git_native", "workspace is not git-native")
        if await self.list():
            raise RemoteError("already_exists", "disconnect the current remote first")
        from dataclasses import replace

        from app.knowledge_store.engines.git import strip_credentials_in_url

        spec = replace(
            spec,
            url=strip_credentials_in_url(spec.url.strip()),
            branch=(spec.branch or "main").strip() or "main",
        )
        provider = provider_for(spec.provider)
        provider.validate(spec)
        creds = await provider.credentials(spec)
        try:
            branches = await asyncio.to_thread(
                lambda: self._engine.list_remote_branches(
                    url=spec.url, username=creds.username, password=creds.password
                )
            )
        except RemoteError:
            raise
        except Exception as exc:
            raise RemoteError("forge", f"could not list remote branches: {exc}") from exc
        if branches.get(spec.branch):
            raise RemoteError("not_empty", f"{spec.branch} already has commits")
        status = await self._rows.save(self._workspace_id, spec)
        await self._session.commit()
        enqueue_push(self._workspace_id)
        return status

    async def remove(self) -> None:
        await self._rows.clear(self._workspace_id)
        await self._session.commit()

    async def credentials(self) -> RemoteCredentials:
        spec = await self._rows.get_spec(self._workspace_id)
        if spec is None:
            raise RemoteError("missing", "no remote configured")
        return await provider_for(spec.provider).credentials(spec)

    async def record_push(self, sha: str) -> None:
        await self._rows.record_push(self._workspace_id, sha)

    async def record_push_failure(self, error: str) -> None:
        await self._rows.record_push_failure(self._workspace_id, error)
