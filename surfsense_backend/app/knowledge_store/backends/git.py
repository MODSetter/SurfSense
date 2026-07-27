"""Git-backed implementation of the versioned content store (via dulwich).

All Git mechanics are confined here; callers see only the
:class:`VersionedContentStore` contract. Every method is synchronous and
self-contained (opens its own repo handle) so it is safe to run in a worker
thread from the async facade.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from dulwich import porcelain
from dulwich.object_store import tree_lookup_path
from dulwich.objects import Blob
from dulwich.repo import Repo

from app.knowledge_store.backends.base import StoredRevision, VersionedContentStore


class GitContentStore(VersionedContentStore):
    """One workspace's history as a Git repository at ``path``."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def ensure(self) -> None:
        self._path.mkdir(parents=True, exist_ok=True)
        if not (self._path / ".git").exists():
            porcelain.init(str(self._path))

    def commit(
        self,
        *,
        writes: Mapping[str, bytes],
        removes: Iterable[str],
        message: str,
        author: str,
    ) -> str | None:
        repo = Repo(str(self._path))
        try:
            for rel_path, data in writes.items():
                abs_path = self._path / rel_path
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_bytes(data)
                porcelain.add(repo, paths=[str(abs_path)])

            for rel_path in removes:
                self._unstage_removal(repo, rel_path)

            if not self._has_pending_changes(repo):
                return None

            author_bytes = author.encode()
            revision = porcelain.commit(
                repo,
                message=message.encode(),
                author=author_bytes,
                committer=author_bytes,
            )
            return revision.decode()
        finally:
            repo.close()

    def read(self, path: str) -> bytes | None:
        abs_path = self._path / path
        return abs_path.read_bytes() if abs_path.is_file() else None

    def read_at(self, revision: str, path: str) -> bytes:
        repo = Repo(str(self._path))
        try:
            tree_id = repo[revision.encode()].tree
            _, blob_sha = tree_lookup_path(repo.get_object, tree_id, path.encode())
            return repo[blob_sha].data
        finally:
            repo.close()

    def history(
        self, *, path: str | None = None, limit: int | None = None
    ) -> list[StoredRevision]:
        repo = Repo(str(self._path))
        try:
            if repo.head() is None:  # pragma: no cover - guarded below
                return []
        except KeyError:
            return []
        try:
            walker = repo.get_walker(
                paths=[path.encode()] if path else None,
                max_entries=limit,
            )
            return [self._to_revision(entry.commit) for entry in walker]
        finally:
            repo.close()

    def head(self) -> str | None:
        repo = Repo(str(self._path))
        try:
            return repo.head().decode()
        except KeyError:
            return None
        finally:
            repo.close()

    @staticmethod
    def content_id(data: bytes) -> str:
        return Blob.from_string(data).id.decode()

    def _unstage_removal(self, repo: Repo, rel_path: str) -> None:
        """Stage a deletion, tolerating a path that was never tracked."""
        if rel_path.encode() not in repo.open_index():
            return
        porcelain.remove(repo, paths=[str(self._path / rel_path)])

    def _has_pending_changes(self, repo: Repo) -> bool:
        """Whether the staged index differs from the current head tree."""
        index_tree = repo.open_index().commit(repo.object_store)
        try:
            head_tree = repo[repo.head()].tree
        except KeyError:
            return True
        return index_tree != head_tree

    @staticmethod
    def _to_revision(commit) -> StoredRevision:
        return StoredRevision(
            id=commit.id.decode(),
            author=commit.author.decode(),
            message=commit.message.decode().strip(),
            created_at=datetime.fromtimestamp(commit.commit_time, tz=UTC),
        )
