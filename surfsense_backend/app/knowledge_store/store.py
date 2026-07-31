"""Public, engine-agnostic API for a workspace's versioned content."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from app.knowledge_store.engines.base import (
    Change,
    Revision,
    TrackedPath,
    VersionedContentEngine,
    WorkingCopy,
)
from app.knowledge_store.engines.git import GitContentEngine
from app.knowledge_store.store_path import (
    workspace_store_path,
    workspace_working_copies_path,
)
from app.knowledge_store.transaction import Transaction
from app.knowledge_store.write_lock import workspace_write_lock


class KnowledgeStore:
    """Versioned content history for one workspace."""

    def __init__(self, workspace_id: int | str, engine: VersionedContentEngine) -> None:
        self._workspace_id = workspace_id
        self._engine = engine

    @classmethod
    def for_workspace(cls, workspace_id: int | str) -> KnowledgeStore:
        """Build a workspace's store; the only place it binds to a concrete engine."""
        engine = GitContentEngine(
            workspace_store_path(workspace_id),
            workspace_working_copies_path(workspace_id),
        )
        return cls(workspace_id, engine)

    @asynccontextmanager
    async def transaction(
        self, *, message: str, author: str, committer: str | None = None
    ):
        """Atomic unit of work: verbs staged in the scope become one revision
        on clean exit; an exception records nothing.

        ``author`` is whose content change this is; ``committer`` (default
        ``author``) is who recorded it — the agent identity for agent turns."""
        tx = Transaction()
        yield tx
        async with workspace_write_lock(self._workspace_id):
            tx.revision = await asyncio.to_thread(
                self._record_revision, tx, message, author, committer
            )

    async def read_as_of(self, revision: str, path: str) -> bytes:
        """Bytes of ``path`` as of ``revision``."""
        return await asyncio.to_thread(self._engine.read_as_of, revision, path)

    async def list_revisions(
        self, *, path: str | None = None, limit: int | None = None
    ) -> list[Revision]:
        """Revisions newest-first, optionally scoped to a single ``path``."""
        return await asyncio.to_thread(
            self._engine.list_revisions, path=path, limit=limit
        )

    async def list_changes(
        self, revision: str, *, since: str | None = None
    ) -> list[Change]:
        """What ``revision`` changed, against its parent or against ``since``."""
        return await asyncio.to_thread(self._engine.list_changes, revision, since=since)

    async def list_paths(self, revision: str) -> list[TrackedPath]:
        """Every path stored at ``revision``, with its content address."""
        return await asyncio.to_thread(self._engine.list_paths, revision)

    async def get_current_revision(self) -> str | None:
        """Id of the workspace's current revision (a whole-workspace snapshot),
        or ``None`` when the store is empty."""
        return await asyncio.to_thread(self._engine.get_current_revision)

    async def open_working_copy(self, copy_id: str) -> WorkingCopy:
        """Private on-disk copy of the current content; reopens an existing one."""
        return await asyncio.to_thread(self._engine.open_working_copy, copy_id)

    async def diff_working_copy(
        self, copy_id: str
    ) -> tuple[dict[str, bytes], list[str]]:
        """Net changes in ``copy_id``'s copy since its base, as ``(writes, removes)``."""
        return await asyncio.to_thread(self._engine.diff_working_copy, copy_id)

    async def discard_working_copy(self, copy_id: str) -> None:
        """Delete ``copy_id``'s working copy; a no-op if absent."""
        await asyncio.to_thread(self._engine.discard_working_copy, copy_id)

    async def prune_working_copies(self, *, older_than_seconds: float) -> list[str]:
        """Delete abandoned working copies; returns the pruned ids."""
        return await asyncio.to_thread(
            lambda: self._engine.prune_working_copies(
                older_than_seconds=older_than_seconds
            )
        )

    def compute_content_id(self, data: bytes) -> str:
        """Content address for ``data`` (no I/O)."""
        return self._engine.compute_content_id(data)

    def _record_revision(
        self, tx: Transaction, message: str, author: str, committer: str | None
    ) -> str | None:
        """Resolve the transaction into one change set and record it."""
        writes, removes = tx.resolve(self._engine.read)
        return self._engine.record(
            writes=writes,
            removes=removes,
            message=message,
            author=author,
            committer=committer,
        )
