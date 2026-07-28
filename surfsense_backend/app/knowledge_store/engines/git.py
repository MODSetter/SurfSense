"""Git implementation of the versioned content engine (dulwich).

Methods are synchronous; the async facade runs them in a worker thread.
Public methods are documented on the contract (``engines/base.py``).
"""

from __future__ import annotations

import shutil
import threading
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from dulwich import porcelain
from dulwich.diff_tree import CHANGE_ADD, CHANGE_DELETE, CHANGE_MODIFY, tree_changes
from dulwich.object_store import iter_tree_contents, tree_lookup_path
from dulwich.objects import Blob
from dulwich.repo import Repo
from dulwich.worktree import add_worktree, prune_worktrees, remove_worktree

from app.knowledge_store.engines.base import (
    Change,
    Revision,
    TrackedPath,
    VersionedContentEngine,
    WorkingCopy,
)

_CHANGE_KINDS = {
    CHANGE_ADD: "added",
    CHANGE_MODIFY: "modified",
    CHANGE_DELETE: "removed",
}

# Serializes working-copy creation against parallel tool calls in one process.
# ponytail: one process-wide lock; open is a stat once the copy exists.
_open_working_copy_lock = threading.Lock()


class GitContentEngine(VersionedContentEngine):
    """One workspace's history as a Git repository at ``path``."""

    def __init__(self, path: Path, working_copies_path: Path) -> None:
        self._path = path
        self._working_copies_path = working_copies_path

    def _ensure_exists(self) -> None:
        """Bootstrap the repository on first use; a no-op once it exists."""
        self._path.mkdir(parents=True, exist_ok=True)
        if not (self._path / ".git").exists():
            porcelain.init(str(self._path))

    def _exists(self) -> bool:
        return (self._path / ".git").exists()

    def record(
        self,
        *,
        writes: Mapping[str, bytes],
        removes: Iterable[str],
        message: str,
        author: str,
        committer: str | None = None,
    ) -> str | None:
        self._ensure_exists()
        repo = Repo(str(self._path))
        try:
            for rel_path, data in writes.items():
                abs_path = self._path / rel_path
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_bytes(data)
                porcelain.add(repo, paths=[str(abs_path)])

            for rel_path in removes:
                self._stage_removal(repo, rel_path)

            if not self._has_pending_changes(repo):
                return None

            revision = porcelain.commit(
                repo,
                message=message.encode(),
                author=author.encode(),
                committer=(committer or author).encode(),
            )
            return revision.decode()
        finally:
            repo.close()

    def read(self, path: str) -> bytes | None:
        abs_path = self._path / path
        return abs_path.read_bytes() if abs_path.is_file() else None

    def read_as_of(self, revision: str, path: str) -> bytes:
        repo = Repo(str(self._path))
        try:
            tree_id = repo[revision.encode()].tree
            _, blob_sha = tree_lookup_path(repo.get_object, tree_id, path.encode())
            return repo[blob_sha].data
        finally:
            repo.close()

    def list_revisions(
        self, *, path: str | None = None, limit: int | None = None
    ) -> list[Revision]:
        if not self._exists():
            return []
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

    def list_changes(self, revision: str) -> list[Change]:
        repo = Repo(str(self._path))
        try:
            commit = repo[revision.encode()]
            parent_tree = repo[commit.parents[0]].tree if commit.parents else None
            changes = []
            for change in tree_changes(repo.object_store, parent_tree, commit.tree):
                kind = _CHANGE_KINDS.get(change.type)
                if kind is None:
                    continue
                entry = change.old if kind == "removed" else change.new
                changes.append(
                    Change(
                        path=entry.path.decode(),
                        kind=kind,
                        content_id=None if kind == "removed" else entry.sha.decode(),
                    )
                )
            return changes
        finally:
            repo.close()

    def list_paths(self, revision: str) -> list[TrackedPath]:
        repo = Repo(str(self._path))
        try:
            tree_id = repo[revision.encode()].tree
            return [
                TrackedPath(path=entry.path.decode(), content_id=entry.sha.decode())
                for entry in iter_tree_contents(repo.object_store, tree_id)
            ]
        finally:
            repo.close()

    def get_current_revision(self) -> str | None:
        if not self._exists():
            return None
        repo = Repo(str(self._path))
        try:
            return repo.head().decode()
        except KeyError:
            return None
        finally:
            repo.close()

    def open_working_copy(self, copy_id: str) -> WorkingCopy:
        with _open_working_copy_lock:
            self._ensure_exists()
            copy_path = self._working_copies_path / copy_id
            if copy_path.exists():
                return WorkingCopy(
                    id=copy_id,
                    path=copy_path,
                    base_revision=self._working_copy_base(copy_path),
                )
            base = self.get_current_revision()
            copy_path.parent.mkdir(parents=True, exist_ok=True)
            if base is None:
                # An empty store has no revision to check out; start from a bare directory.
                copy_path.mkdir()
            else:
                repo = Repo(str(self._path))
                try:
                    add_worktree(repo, str(copy_path), detach=True).close()
                finally:
                    repo.close()
            return WorkingCopy(id=copy_id, path=copy_path, base_revision=base)

    def diff_working_copy(self, copy_id: str) -> tuple[dict[str, bytes], list[str]]:
        copy_path = self._working_copies_path / copy_id
        if not copy_path.is_dir():
            raise FileNotFoundError(f"No working copy '{copy_id}'")
        if self._working_copy_base(copy_path) is None:
            return self._all_files_as_writes(copy_path), []

        status = porcelain.status(str(copy_path), untracked_files="all")
        writes: dict[str, bytes] = {}
        removes: list[str] = []
        for raw in status.untracked:
            rel = raw.decode() if isinstance(raw, bytes) else raw
            writes[rel] = (copy_path / rel).read_bytes()
        for raw in status.unstaged:
            rel = raw.decode() if isinstance(raw, bytes) else raw
            file = copy_path / rel
            if file.is_file():
                writes[rel] = file.read_bytes()
            else:
                removes.append(rel)
        return writes, removes

    def discard_working_copy(self, copy_id: str) -> None:
        copy_path = self._working_copies_path / copy_id
        if not copy_path.exists():
            return
        if (copy_path / ".git").exists():
            repo = Repo(str(self._path))
            try:
                remove_worktree(repo, str(copy_path), force=True)
            finally:
                repo.close()
        else:
            shutil.rmtree(copy_path)

    def prune_working_copies(self, *, older_than_seconds: float) -> list[str]:
        # ponytail: age = the copy directory's own mtime (not nested files), so the
        # threshold must exceed the longest plausible unit of work by a wide margin.
        if not self._working_copies_path.exists():
            return []
        cutoff = time.time() - older_than_seconds
        pruned = [
            entry.name
            for entry in self._working_copies_path.iterdir()
            if entry.is_dir() and entry.stat().st_mtime < cutoff
        ]
        for copy_id in pruned:
            self.discard_working_copy(copy_id)
        if (self._path / ".git").exists():
            repo = Repo(str(self._path))
            try:
                # Drop bookkeeping left by copies whose directory vanished (e.g. a crash).
                prune_worktrees(repo, expire=0)
            finally:
                repo.close()
        return pruned

    @staticmethod
    def compute_content_id(data: bytes) -> str:
        return Blob.from_string(data).id.decode()

    @staticmethod
    def _working_copy_base(copy_path: Path) -> str | None:
        """Revision an existing copy was opened at (``None`` for a bare directory)."""
        if not (copy_path / ".git").exists():
            return None
        repo = Repo(str(copy_path))
        try:
            return repo.head().decode()
        finally:
            repo.close()

    @staticmethod
    def _all_files_as_writes(copy_path: Path) -> dict[str, bytes]:
        return {
            str(file.relative_to(copy_path)): file.read_bytes()
            for file in sorted(copy_path.rglob("*"))
            if file.is_file() and ".git" not in file.relative_to(copy_path).parts
        }

    def _stage_removal(self, repo: Repo, rel_path: str) -> None:
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
    def _to_revision(commit) -> Revision:
        return Revision(
            id=commit.id.decode(),
            author=commit.author.decode(),
            committer=commit.committer.decode(),
            message=commit.message.decode().strip(),
            created_at=datetime.fromtimestamp(commit.commit_time, tz=UTC),
        )
