"""Public, engine-agnostic API for a workspace's versioned content."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from app.knowledge_store.backends.base import StoredRevision, VersionedContentStore
from app.knowledge_store.backends.git import GitContentStore
from app.knowledge_store.store_path import workspace_store_path
from app.knowledge_store.revision_draft import RevisionDraft
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
        await asyncio.to_thread(self._backend.ensure)

    @asynccontextmanager
    async def revise(self, *, message: str, author: str):
        """Record the scope's verbs as one revision on clean exit; nothing on error."""
        draft = RevisionDraft()
        yield draft
        async with workspace_write_lock(self._workspace_id):
            draft.revision = await asyncio.to_thread(
                self._record_revision, draft, message, author
            )

    async def read_at(self, revision: str, path: str) -> bytes:
        """Bytes of ``path`` as of a past ``revision``."""
        return await asyncio.to_thread(self._backend.read_at, revision, path)

    async def history(
        self, *, path: str | None = None, limit: int | None = None
    ) -> list[StoredRevision]:
        """Revisions newest-first, optionally scoped to a single ``path``."""
        return await asyncio.to_thread(self._backend.history, path=path, limit=limit)

    async def current_revision(self) -> str | None:
        """Id of the current revision, or ``None`` when the store is empty."""
        return await asyncio.to_thread(self._backend.current_revision)

    def content_id(self, data: bytes) -> str:
        """Content address for ``data`` (no I/O)."""
        return self._backend.content_id(data)

    def _record_revision(
        self, draft: RevisionDraft, message: str, author: str
    ) -> str | None:
        """Collapse the draft's verbs into one change set and commit it."""
        writes, removes = draft.to_change_set(self._backend.read)
        return self._backend.commit(
            writes=writes, removes=removes, message=message, author=author
        )
