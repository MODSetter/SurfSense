"""A workspace's git remotes. v1: at most one destination."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.forges import provider_for
from app.knowledge_store.remote.paths import full_name_from_url, mount
from app.knowledge_store.remote.persistence import WorkspaceRemoteRepository
from app.knowledge_store.remote.shadow import Shadow, shadow_path
from app.knowledge_store.remote.sync import apply_from_remote, text_under_mount
from app.knowledge_store.remote.schemas import (
    RemoteCredentials,
    RemoteSpec,
    RemoteStatus,
)
from app.knowledge_store.settings import knowledge_store_enabled_for
from app.observability.domains import knowledge_store as ks_telemetry

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

    async def add(
        self, spec: RemoteSpec, *, direction: str | None = None
    ) -> RemoteStatus:
        with ks_telemetry.remote_connect_span(
            workspace_id=self._workspace_id,
            provider=spec.provider,
            extra={
                "remote.sourcepath": spec.sourcepath or "",
                "remote.direction": direction or "",
            },
        ) as sp:
            try:
                status = await self._add(spec, direction=direction)
            except RemoteError as exc:
                sp.set_attribute("connect.status", "rejected")
                sp.set_attribute("connect.code", exc.code)
                ks_telemetry.record_knowledge_store_remote_connect(
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
            ks_telemetry.record_knowledge_store_remote_connect(
                provider=spec.provider, status="connected"
            )
            logger.info(
                "Git remote connected workspace=%s provider=%s",
                self._workspace_id,
                spec.provider,
            )
            return status

    async def _add(
        self, spec: RemoteSpec, *, direction: str | None = None
    ) -> RemoteStatus:
        if not await knowledge_store_enabled_for(self._workspace_id):
            raise RemoteError("not_git_native", "workspace is not git-native")
        if await self.list():
            raise RemoteError("already_exists", "disconnect the current remote first")
        from dataclasses import replace

        from app.knowledge_store import KnowledgeStore
        from app.knowledge_store.engines.git import strip_credentials_in_url

        spec = replace(
            spec,
            url=strip_credentials_in_url(spec.url.strip()),
            branch=(spec.branch or "main").strip() or "main",
            sourcepath=(spec.sourcepath or "").strip("/"),
        )
        provider = provider_for(spec.provider)
        provider.validate(spec)
        creds = await provider.credentials(spec)
        try:
            await asyncio.to_thread(
                lambda: self._engine.list_remote_branches(
                    url=spec.url, username=creds.username, password=creds.password
                )
            )
        except RemoteError:
            raise
        except Exception as exc:
            raise RemoteError("forge", f"could not list remote branches: {exc}") from exc
        prefix = mount(
            provider=spec.provider,
            full_name=full_name_from_url(spec.url),
            sourcepath=spec.sourcepath,
        )
        pending = shadow_path(self._workspace_id, 0)
        if pending.exists():
            import shutil

            shutil.rmtree(pending)
        try:
            with ks_telemetry.remote_shadow_span(
                workspace_id=self._workspace_id, operation="clone"
            ):
                shadow = await asyncio.to_thread(
                    lambda: Shadow.clone(spec.url, pending, branch=spec.branch)
                )
        except Exception as exc:
            raise RemoteError("forge", f"could not clone remote: {exc}") from exc
        remote_docs = shadow.list_text(spec.sourcepath)
        store = KnowledgeStore.for_workspace(self._workspace_id).with_session(
            self._session
        )
        local_docs = await text_under_mount(store, prefix)
        # Both sides already hold documents and the caller named no winner: connect
        # anyway, mirror nothing, and flag the row so the card asks which side to
        # keep (resolve from_remote / from_local).
        needs_direction = bool(remote_docs) and bool(local_docs) and direction is None
        await self._rows.save(self._workspace_id, spec)
        await self._session.flush()
        row = (await self._rows._rows(self._workspace_id))[0]
        dest = shadow_path(self._workspace_id, int(row.id))
        dest.parent.mkdir(parents=True, exist_ok=True)
        pending.rename(dest)
        pulled = (
            bool(remote_docs)
            and not needs_direction
            and (direction is None or direction == "from_remote")
        )
        if pulled:
            await apply_from_remote(store, mount=prefix, files=remote_docs)
        shadow = Shadow(dest)
        head = await store.head()
        row.last_remote_sha = shadow.head_sha()
        row.last_local_revision = head
        if needs_direction:
            row.last_error_code = "need_direction"
        elif pulled:
            _mark_synced(row, head)
        await self._session.commit()
        return (await self.list())[0]

    async def remove(self) -> None:
        import shutil

        with ks_telemetry.remote_disconnect_span(
            workspace_id=self._workspace_id
        ) as sp:
            remotes = await self.list()
            provider = remotes[0].provider if remotes else None
            if provider:
                sp.set_attribute("remote.provider", provider)
            leftover = shadow_path(self._workspace_id, 0).parent
            if leftover.exists():
                shutil.rmtree(leftover)
            await self._rows.clear(self._workspace_id)
            await self._session.commit()
            ks_telemetry.record_knowledge_store_remote_disconnect(provider=provider)
            logger.info(
                "Git remote disconnected workspace=%s provider=%s",
                self._workspace_id,
                provider or "none",
            )

    async def sync(self) -> str | None:
        """Fetch, 3-way, apply, pathspec-push. No-op when nothing is connected."""
        with ks_telemetry.remote_sync_span(workspace_id=self._workspace_id) as sp:
            try:
                return await self._sync(sp)
            except RemoteError as exc:
                _observe_sync(
                    sp,
                    self._workspace_id,
                    status="failed",
                    error_code=exc.code,
                )
                raise
            except Exception:
                _observe_sync(
                    sp,
                    self._workspace_id,
                    status="failed",
                    error_code="forge",
                )
                raise

    async def _sync(self, sp) -> str | None:
        from app.knowledge_store import KnowledgeStore
        from app.knowledge_store.identities import AGENT_IDENTITY
        from app.knowledge_store.exceptions import GitPushError
        from app.knowledge_store.remote.planner import SyncConflict, plan
        from app.knowledge_store.remote.sync import apply_changes, text_under_mount

        rows = await self._rows._rows(self._workspace_id)
        if not rows:
            _observe_sync(sp, self._workspace_id, status="skipped")
            return None
        row = rows[0]
        spec = await self._rows.get_spec(self._workspace_id)
        if spec is None:
            _observe_sync(sp, self._workspace_id, status="skipped")
            return None
        if row.last_error_code in {"conflict", "need_direction"}:
            _observe_sync(
                sp,
                self._workspace_id,
                status="blocked",
                provider=spec.provider,
                error_code=row.last_error_code,
            )
            return None
        from app.knowledge_store.paths import workspace_working_copies_path

        copies = workspace_working_copies_path(self._workspace_id)
        if copies.is_dir() and any(p.is_dir() for p in copies.iterdir()):
            row.last_error_code = "worktree_busy"
            await self._session.flush()
            _observe_sync(
                sp,
                self._workspace_id,
                status="worktree_busy",
                provider=spec.provider,
            )
            return None
        prefix = mount(
            provider=spec.provider,
            full_name=full_name_from_url(spec.url),
            sourcepath=spec.sourcepath,
        )
        store = KnowledgeStore.for_workspace(self._workspace_id).with_session(
            self._session
        )
        shadow = Shadow(shadow_path(self._workspace_id, int(row.id)))
        with ks_telemetry.remote_shadow_span(
            workspace_id=self._workspace_id, operation="refresh"
        ):
            await asyncio.to_thread(
                lambda: shadow.refresh(spec.url, branch=spec.branch)
            )
        local_docs = await text_under_mount(store, prefix)
        remote_docs = shadow.list_text(spec.sourcepath)
        base = await text_under_mount(
            store, prefix, revision=row.last_local_revision
        )
        result = plan(base=base, local=local_docs, remote=remote_docs)
        if isinstance(result, SyncConflict):
            row.last_error_code = "conflict"
            row.last_conflict_paths = "\n".join(result.paths)
            await self._session.flush()
            _observe_sync(
                sp,
                self._workspace_id,
                status="conflict",
                provider=spec.provider,
            )
            return None
        if result.apply_local:
            await apply_changes(store, mount=prefix, changes=result.apply_local)
            local_docs = await text_under_mount(store, prefix)
        creds = await self.credentials()

        def _push() -> str | None:
            shadow.replace_text(spec.sourcepath, local_docs)
            shadow.commit(message="sync from SurfSense", author=AGENT_IDENTITY)
            return shadow.push(
                url=spec.url,
                ref=f"refs/heads/{spec.branch}",
                username=creds.username,
                password=creds.password,
            )

        try:
            with ks_telemetry.remote_shadow_span(
                workspace_id=self._workspace_id, operation="push"
            ):
                sha = await asyncio.to_thread(_push)
        except GitPushError as exc:
            raise RemoteError("forge", str(exc)) from exc
        head = await store.head()
        row.last_remote_sha = sha
        row.last_local_revision = head
        row.last_error_code = None
        row.last_conflict_paths = None
        _mark_synced(row, head)
        await self._session.flush()
        _observe_sync(
            sp, self._workspace_id, status="mirrored", provider=spec.provider
        )
        return sha

    async def resolve(self, *, direction: str) -> None:
        """Overwrite one side of the bijection, then stamp a new base."""
        with ks_telemetry.remote_resolve_span(
            workspace_id=self._workspace_id, direction=direction
        ) as sp:
            try:
                provider = await self._resolve(direction)
                await self._session.commit()
            except RemoteError as exc:
                sp.set_attribute("resolve.status", "failed")
                sp.set_attribute("resolve.error_code", exc.code)
                ks_telemetry.record_knowledge_store_remote_resolve(
                    direction=direction, status="failed"
                )
                logger.info(
                    "Git remote resolve failed workspace=%s direction=%s code=%s",
                    self._workspace_id,
                    direction,
                    exc.code,
                )
                raise
            except Exception:
                sp.set_attribute("resolve.status", "failed")
                ks_telemetry.record_knowledge_store_remote_resolve(
                    direction=direction, status="failed"
                )
                raise
            sp.set_attribute("resolve.status", "resolved")
            if provider:
                sp.set_attribute("remote.provider", provider)
            ks_telemetry.record_knowledge_store_remote_resolve(
                direction=direction, status="resolved", provider=provider
            )
            logger.info(
                "Git remote resolved workspace=%s direction=%s provider=%s",
                self._workspace_id,
                direction,
                provider or "none",
            )

    async def _resolve(self, direction: str) -> str:
        from app.knowledge_store import KnowledgeStore
        from app.knowledge_store.identities import AGENT_IDENTITY
        from app.knowledge_store.remote.paths import to_local
        from app.knowledge_store.remote.sync import text_under_mount

        if direction not in {"from_remote", "from_local"}:
            raise RemoteError(
                "invalid_spec", "direction must be from_remote or from_local"
            )
        rows = await self._rows._rows(self._workspace_id)
        if not rows:
            raise RemoteError("missing", "no remote configured")
        row = rows[0]
        spec = await self._rows.get_spec(self._workspace_id)
        if spec is None:
            raise RemoteError("missing", "no remote configured")
        prefix = mount(
            provider=spec.provider,
            full_name=full_name_from_url(spec.url),
            sourcepath=spec.sourcepath,
        )
        store = KnowledgeStore.for_workspace(self._workspace_id).with_session(
            self._session
        )
        shadow = Shadow(shadow_path(self._workspace_id, int(row.id)))
        with ks_telemetry.remote_shadow_span(
            workspace_id=self._workspace_id, operation="refresh"
        ):
            await asyncio.to_thread(
                lambda: shadow.refresh(spec.url, branch=spec.branch)
            )
        remote_docs = shadow.list_text(spec.sourcepath)
        local_docs = await text_under_mount(store, prefix)
        if direction == "from_remote":
            async with store.transaction(
                message="resolve from remote", author=AGENT_IDENTITY
            ) as tx:
                for rel, content in remote_docs.items():
                    tx.write(to_local(mount=prefix, rel=rel), content)
                for rel in local_docs:
                    if rel not in remote_docs:
                        tx.remove(to_local(mount=prefix, rel=rel))
        else:
            creds = await self.credentials()

            def _push_local() -> str:
                shadow.replace_text(spec.sourcepath, local_docs)
                shadow.commit(message="resolve from SurfSense", author=AGENT_IDENTITY)
                return shadow.push(
                    url=spec.url,
                    ref=f"refs/heads/{spec.branch}",
                    username=creds.username,
                    password=creds.password,
                )

            from app.knowledge_store.exceptions import GitPushError

            try:
                with ks_telemetry.remote_shadow_span(
                    workspace_id=self._workspace_id, operation="push"
                ):
                    await asyncio.to_thread(_push_local)
            except GitPushError as exc:
                raise RemoteError("forge", str(exc)) from exc
        row.last_error_code = None
        row.last_conflict_paths = None
        row.last_remote_sha = shadow.head_sha()
        head = await store.head()
        row.last_local_revision = head
        _mark_synced(row, head)
        await self._session.flush()
        return spec.provider

    async def credentials(self) -> RemoteCredentials:
        spec = await self._rows.get_spec(self._workspace_id)
        if spec is None:
            raise RemoteError("missing", "no remote configured")
        return await provider_for(spec.provider).credentials(spec)

    async def record_push(self, sha: str) -> None:
        await self._rows.record_push(self._workspace_id, sha)

    async def record_push_failure(self, error: str) -> None:
        await self._rows.record_push_failure(self._workspace_id, error)


def _mark_synced(row, revision: str | None) -> None:
    """Stamp the display marker the card reads (``last_pushed_*`` == last synced).

    The 3-way base is ``last_local_revision``/``last_remote_sha``; these fields
    are only what the UI shows, so a pull or a mirror both count as "synced".
    """
    if revision is None:
        return
    row.last_pushed_revision = revision
    row.last_pushed_at = datetime.now(UTC)
    row.last_push_error = None


def _observe_sync(
    sp,
    workspace_id: int,
    *,
    status: str,
    provider: str | None = None,
    error_code: str | None = None,
) -> None:
    sp.set_attribute("sync.status", status)
    if provider:
        sp.set_attribute("remote.provider", provider)
    if error_code:
        sp.set_attribute("sync.error_code", error_code)
    ks_telemetry.record_knowledge_store_remote_sync(
        status=status, provider=provider, error_code=error_code
    )
    logger.info(
        "Git remote sync workspace=%s status=%s provider=%s",
        workspace_id,
        status,
        provider or "none",
    )
