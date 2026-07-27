"""The knowledge store's public surface: an engine-agnostic, async facade.

Callers work a workspace's versioned history through this class and never see
Git. Reads run lock-free. Mutations go through :meth:`KnowledgeStore.revise` —
a unit-of-work scope whose intent verbs (``write``/``remove``/``move``) record
one atomic revision on exit, serialized per workspace. Whether that revision
touches one file or fifty is an engine detail, not part of this API.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager

from app.knowledge_store.backends.base import StoredRevision, VersionedContentStore
from app.knowledge_store.backends.git import GitContentStore
from app.knowledge_store.locations import workspace_store_path
from app.knowledge_store.write_lock import workspace_write_lock


class RevisionDraft:
    """Changes staged for one revision, expressed as intent verbs.

    Verbs only record intent (no I/O); the store applies and commits them
    atomically when the :meth:`KnowledgeStore.revise` scope exits.
    """

    def __init__(self) -> None:
        self._writes: dict[str, bytes] = {}
        self._removes: list[str] = []
        self._moves: list[tuple[str, str]] = []
        #: Id of the recorded revision, set on scope exit (``None`` if no change).
        self.revision: str | None = None

    def write(self, path: str, content: bytes) -> None:
        """Create or replace ``path`` with ``content``."""
        self._writes[path] = content
        if path in self._removes:
            self._removes.remove(path)

    def remove(self, path: str) -> None:
        """Delete ``path``."""
        self._writes.pop(path, None)
        if path not in self._removes:
            self._removes.append(path)

    def move(self, src: str, dst: str) -> None:
        """Relocate ``src`` to ``dst`` (source content is carried over)."""
        self._moves.append((src, dst))

    def resolve(
        self, read_source: Callable[[str], bytes | None]
    ) -> tuple[dict[str, bytes], list[str]]:
        """Flatten verbs into a write/remove batch for the engine.

        A move becomes write-destination + remove-source, using the source's
        current bytes (``read_source``) unless it was (re)written in this scope.
        """
        writes = dict(self._writes)
        removes = list(self._removes)
        for src, dst in self._moves:
            content = writes.pop(src, None)
            if content is None:
                content = read_source(src)
            if content is None:
                raise FileNotFoundError(f"cannot move missing path: {src}")
            writes[dst] = content
            removes.append(src)
        return writes, removes


class KnowledgeStore:
    """Versioned content history for one workspace."""

    def __init__(self, workspace_id: int | str, backend: VersionedContentStore) -> None:
        self._workspace_id = workspace_id
        self._backend = backend

    @classmethod
    def for_workspace(cls, workspace_id: int | str) -> KnowledgeStore:
        # The single seam that binds a workspace to the Git engine; swapping
        # engines happens here and nowhere else.
        backend = GitContentStore(workspace_store_path(workspace_id))
        return cls(workspace_id, backend)

    async def ensure(self) -> None:
        await asyncio.to_thread(self._backend.ensure)

    @asynccontextmanager
    async def revise(self, *, message: str, author: str):
        """Open a revision scope; its verbs commit atomically on clean exit.

        On exception the scope makes no change. On success the workspace write
        lock is held only for the single commit.
        """
        draft = RevisionDraft()
        yield draft
        async with workspace_write_lock(self._workspace_id):
            draft.revision = await asyncio.to_thread(
                self._record, draft, message, author
            )

    async def read_at(self, revision: str, path: str) -> bytes:
        return await asyncio.to_thread(self._backend.read_at, revision, path)

    async def history(
        self, *, path: str | None = None, limit: int | None = None
    ) -> list[StoredRevision]:
        return await asyncio.to_thread(self._backend.history, path=path, limit=limit)

    async def head(self) -> str | None:
        return await asyncio.to_thread(self._backend.head)

    def content_id(self, data: bytes) -> str:
        """Stable content address for ``data`` (pure; no I/O, no lock)."""
        return self._backend.content_id(data)

    def _record(self, draft: RevisionDraft, message: str, author: str) -> str | None:
        """Snapshot a draft as one revision (inside the lock, on a worker thread)."""
        writes, removes = draft.resolve(self._backend.read)
        return self._backend.commit(
            writes=writes, removes=removes, message=message, author=author
        )
