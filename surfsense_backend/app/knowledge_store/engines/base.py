"""Storage-engine contract behind the facade; the seam for swapping engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

ChangeKind = Literal["added", "modified", "removed"]


@dataclass(frozen=True)
class Revision:
    """One recorded point in a workspace's history (a whole-tree snapshot)."""

    id: str
    #: Whose content change this is (the acting user).
    author: str
    #: Who recorded it (the agent for agent turns; equals author otherwise).
    committer: str
    message: str
    created_at: datetime


@dataclass(frozen=True)
class Change:
    """One path's change within a revision."""

    path: str
    kind: ChangeKind
    #: Content address after the change (``None`` when removed).
    content_id: str | None


@dataclass(frozen=True)
class TrackedPath:
    """One path stored at a revision, with its content address."""

    path: str
    content_id: str


@dataclass(frozen=True)
class WorkingCopy:
    """A private on-disk copy of the store's content, open for one unit of work."""

    id: str
    path: Path
    #: Revision the copy was opened at (``None`` when the store was empty).
    base_revision: str | None


class VersionedContentEngine(ABC):
    """Append-only, content-addressed history for a single workspace.

    First use bootstraps the store; callers never create it explicitly.
    """

    @abstractmethod
    def record(
        self,
        *,
        writes: Mapping[str, bytes],
        removes: Iterable[str],
        message: str,
        author: str,
        committer: str | None = None,
    ) -> str | None:
        """Append ``writes`` and ``removes`` to history as one revision.

        ``committer`` defaults to ``author``. Returns the revision id, or
        ``None`` when nothing changed.
        """

    @abstractmethod
    def read(self, path: str) -> bytes | None:
        """Current bytes of ``path``, or ``None`` if it does not exist."""

    @abstractmethod
    def read_as_of(self, revision: str, path: str) -> bytes:
        """Bytes of ``path`` as of ``revision``. Raises if absent there."""

    @abstractmethod
    def list_revisions(
        self, *, path: str | None = None, limit: int | None = None
    ) -> list[Revision]:
        """Revisions newest-first, optionally scoped to a single path."""

    @abstractmethod
    def list_changes(self, revision: str) -> list[Change]:
        """Paths added, modified, or removed by ``revision`` (vs its parent)."""

    @abstractmethod
    def list_paths(self, revision: str) -> list[TrackedPath]:
        """Every path stored at ``revision``, with its content address."""

    @abstractmethod
    def get_current_revision(self) -> str | None:
        """Id of the current whole-store snapshot, or ``None`` when empty."""

    @abstractmethod
    def open_working_copy(self, copy_id: str) -> WorkingCopy:
        """Copy of the current content for ``copy_id``; reopens an existing one."""

    @abstractmethod
    def diff_working_copy(self, copy_id: str) -> tuple[dict[str, bytes], list[str]]:
        """Net changes in ``copy_id``'s copy since its base, as ``(writes, removes)``.

        Raises ``FileNotFoundError`` when the copy was never opened.
        """

    @abstractmethod
    def discard_working_copy(self, copy_id: str) -> None:
        """Delete ``copy_id``'s working copy; a no-op if absent."""

    @abstractmethod
    def prune_working_copies(self, *, older_than_seconds: float) -> list[str]:
        """Delete abandoned working copies; returns the pruned ids."""

    @staticmethod
    @abstractmethod
    def compute_content_id(data: bytes) -> str:
        """Stable content address for ``data``, independent of any path."""
