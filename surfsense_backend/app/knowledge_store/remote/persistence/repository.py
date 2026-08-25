"""Postgres access for workspace git remotes. No git, no GitHub HTTP."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.config import config
from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.persistence.models import WorkspaceGitRemotes
from app.knowledge_store.remote.schemas import (
    GithubSpec,
    GitlabSpec,
    RemoteSpec,
    RemoteStatus,
)
from app.utils.oauth_security import TokenEncryption

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class WorkspaceRemoteRepository:
    """Read/write ``workspace_git_remotes``. v1: at most one row per workspace."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_statuses(self, workspace_id: int) -> list[RemoteStatus]:
        return [_status(row) for row in await self._rows(workspace_id)]

    async def get_spec(self, workspace_id: int) -> RemoteSpec | None:
        """Spec including secrets, for ``credentials()`` only."""
        rows = await self._rows(workspace_id)
        if not rows:
            return None
        row = rows[0]
        if row.provider == "github":
            if not row.installation_id:
                raise RemoteError("invalid_spec", "GitHub App installation id is required")
            return GithubSpec(
                provider="github",
                url=row.url,
                installation_id=row.installation_id,
                branch=row.branch or "main",
            )
        if row.provider == "gitlab":
            if not row.token:
                raise RemoteError("invalid_spec", "GitLab PAT is required")
            try:
                token = TokenEncryption(config.SECRET_KEY).decrypt_token(row.token)
            except ValueError as exc:
                raise RemoteError("forge", "could not decrypt GitLab PAT") from exc
            return GitlabSpec(
                provider="gitlab",
                url=row.url,
                token=token,
                branch=row.branch or "main",
            )
        raise RemoteError("invalid_spec", f"unknown provider {row.provider!r}")

    async def save(self, workspace_id: int, spec: RemoteSpec) -> RemoteStatus:
        token = None
        installation_id = None
        if isinstance(spec, GitlabSpec):
            token = TokenEncryption(config.SECRET_KEY).encrypt_token(spec.token)
        elif isinstance(spec, GithubSpec):
            installation_id = spec.installation_id
        rows = await self._rows(workspace_id)
        if rows:
            row = rows[0]
        else:
            row = WorkspaceGitRemotes(workspace_id=workspace_id)
            self._session.add(row)
        row.provider = spec.provider
        row.url = spec.url
        row.branch = spec.branch or "main"
        row.installation_id = installation_id
        row.token = token
        row.last_pushed_revision = None
        row.last_pushed_at = None
        row.last_push_error = None
        await self._session.flush()
        return _status(row)

    async def clear(self, workspace_id: int) -> None:
        for row in await self._rows(workspace_id):
            await self._session.delete(row)
        await self._session.flush()

    async def record_push(self, workspace_id: int, sha: str) -> None:
        rows = await self._rows(workspace_id)
        if not rows:
            return
        row = rows[0]
        row.last_pushed_revision = sha
        row.last_pushed_at = datetime.now(UTC)
        row.last_push_error = None
        await self._session.flush()

    async def record_push_failure(self, workspace_id: int, error: str) -> None:
        rows = await self._rows(workspace_id)
        if not rows:
            return
        rows[0].last_push_error = error
        await self._session.flush()

    async def _rows(self, workspace_id: int) -> list[WorkspaceGitRemotes]:
        result = await self._session.execute(
            select(WorkspaceGitRemotes).where(
                WorkspaceGitRemotes.workspace_id == workspace_id
            )
        )
        return list(result.scalars().all())


def _status(row: WorkspaceGitRemotes) -> RemoteStatus:
    return RemoteStatus(
        provider=row.provider,  # type: ignore[arg-type]
        url=row.url,
        branch=row.branch or "main",
        last_pushed_revision=row.last_pushed_revision,
        last_pushed_at=row.last_pushed_at,
        last_push_error=row.last_push_error,
    )
