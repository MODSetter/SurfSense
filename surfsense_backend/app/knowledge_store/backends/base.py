"""The versioned-content-store contract: the engine surface the facade depends on.

This is the *engine* boundary, and it thinks in tree snapshots — ``commit``
applies a whole batch of changes as one revision. The intent verbs
(``write``/``remove``/``move``) live one layer up on the ``KnowledgeStore``
facade; the batch is an engine detail callers never see. Keeping this an
explicit interface leaves the door open for a second engine (e.g. a native-git
binding) without touching any caller.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoredRevision:
    """One recorded point in a workspace's history."""

    id: str
    author: str
    message: str
    created_at: datetime


class VersionedContentStore(ABC):
    """Append-only, content-addressed history for a single workspace."""

    @abstractmethod
    def ensure(self) -> None:
        """Create the store if absent; a no-op once it exists."""

    @abstractmethod
    def commit(
        self,
        *,
        writes: Mapping[str, bytes],
        removes: Iterable[str],
        message: str,
        author: str,
    ) -> str | None:
        """Snapshot ``writes`` and ``removes`` as one revision (engine primitive).

        Returns the new revision id, or ``None`` when the changes leave the
        content identical to the current head (nothing to record).
        """

    @abstractmethod
    def read(self, path: str) -> bytes | None:
        """Current bytes of ``path`` at head, or ``None`` if it does not exist."""

    @abstractmethod
    def read_at(self, revision: str, path: str) -> bytes:
        """Return a path's bytes as of ``revision``. Raises if absent there."""

    @abstractmethod
    def history(
        self, *, path: str | None = None, limit: int | None = None
    ) -> list[StoredRevision]:
        """Revisions newest-first, optionally scoped to a single path."""

    @abstractmethod
    def head(self) -> str | None:
        """The current head revision id, or ``None`` for an empty store."""

    @staticmethod
    @abstractmethod
    def content_id(data: bytes) -> str:
        """Stable content address for ``data``, independent of any path."""
