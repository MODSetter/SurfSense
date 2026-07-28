"""Public, engine-agnostic API for a workspace's versioned content."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from app.knowledge_store.backends.base import (
    Change,
    Revision,
    TrackedPath,
    VersionedContentStore,
)
from app.knowledge_store.backends.git import GitContentStore
from app.knowledge_store.store_path import workspace_store_path
from app.knowledge_store.transaction import Transaction
from app.knowledge_store.write_lock import workspace_write_lock


class KnowledgeStore:
    """Versioned content history for one workspace."""

    def __init__(self, workspace_id: int | str, backend: VersionedContentStore) -> None:
        self._workspace_id = workspace_id
        self._backend = backend

    @classmethod
    def for_workspace(cls, workspace_id: int | str) -> KnowledgeStore:
        """Build a workspace's store; the only place it binds to a concrete engine."""
        backend = GitContentStore(workspace_store_path(workspace_id))
        return cls(workspace_id, backend)

    async def ensure_exists(self) -> None:
        """Create the workspace's store if it is not there yet (idempotent)."""
        await asyncio.to_thread(self._backend.ensure_exists)

    @asynccontextmanager
    async def transaction(self, *, message: str, author: str):
        """Atomic unit of work: verbs staged in the scope become one revision
        on clean exit; an exception records nothing."""
        tx = Transaction()
        yield tx
        async with workspace_write_lock(self._workspace_id):
            tx.revision = await asyncio.to_thread(
                self._record_revision, tx, message, author
            )

    async def read_as_of(self, revision: str, path: str) -> bytes:
        """Bytes of ``path`` as of ``revision``."""
        return await asyncio.to_thread(self._backend.read_as_of, revision, path)

    async def list_revisions(
        self, *, path: str | None = None, limit: int | None = None
    ) -> list[Revision]:
        """Revisions newest-first, optionally scoped to a single ``path``."""
        return await asyncio.to_thread(self._backend.list_revisions, path=path, limit=limit)

    async def list_changes(self, revision: str) -> list[Change]:
        """Paths added, modified, or removed by ``revision`` (vs its parent)."""
        return await asyncio.to_thread(self._backend.list_changes, revision)

    async def list_paths(self, revision: str) -> list[TrackedPath]:
        """Every path stored at ``revision``, with its content address."""
        return await asyncio.to_thread(self._backend.list_paths, revision)

    async def get_current_revision(self) -> str | None:
        """Id of the workspace's current revision (a whole-workspace snapshot),
        or ``None`` when the store is empty."""
        return await asyncio.to_thread(self._backend.get_current_revision)

    def compute_content_id(self, data: bytes) -> str:
        """Content address for ``data`` (no I/O)."""
        return self._backend.compute_content_id(data)

    def _record_revision(
        self, tx: Transaction, message: str, author: str
    ) -> str | None:
        """Resolve the transaction into one change set and record it."""
        writes, removes = tx.resolve(self._backend.read)
        return self._backend.record(
            writes=writes, removes=removes, message=message, author=author
        )
