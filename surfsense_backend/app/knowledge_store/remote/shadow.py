"""Checkout of their repo. Pathspec writes; never git add -A."""

from __future__ import annotations

import shutil
from pathlib import Path

from dulwich import porcelain
from dulwich.diff_tree import CHANGE_DELETE, tree_changes
from dulwich.porcelain import DivergedBranches
from dulwich.repo import Repo

from app.knowledge_store.engines.git import strip_credentials_in_url
from app.knowledge_store.exceptions import GitPushError
from app.knowledge_store.paths.layout import workspace_store_path
from app.knowledge_store.remote.guards import check_staged
from app.knowledge_store.remote.paths import to_remote


def shadow_path(workspace_id: int | str, remote_id: int) -> Path:
    """Forge clone lives next to the store, never inside its working tree."""
    return workspace_store_path(workspace_id).parent / ".remotes" / str(workspace_id) / str(
        remote_id
    )


class Shadow:
    """Working copy of the forge repo, separate from the workspace store."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @classmethod
    def clone(cls, url: str, dest: Path, *, branch: str | None = None) -> Shadow:
        dest.parent.mkdir(parents=True, exist_ok=True)
        _clone(url, dest, branch=branch)
        return cls(dest)

    def refresh(self, url: str, *, branch: str | None = None) -> None:
        shutil.rmtree(self._path)
        _clone(url, self._path, branch=branch)

    def read(self, path: str) -> bytes | None:
        file = self._path / path
        return file.read_bytes() if file.is_file() else None

    def list_md(self, sourcepath: str) -> dict[str, bytes]:
        root = self._path / sourcepath.strip("/") if sourcepath.strip("/") else self._path
        if not root.is_dir():
            return {}
        found: dict[str, bytes] = {}
        for file in root.rglob("*.md"):
            if ".git" in file.relative_to(self._path).parts:
                continue
            found[file.relative_to(root).as_posix()] = file.read_bytes()
        return found

    def replace_md(self, sourcepath: str, files: dict[str, bytes]) -> None:
        current = self.list_md(sourcepath)
        writes = []
        for rel, content in files.items():
            remote = to_remote(sourcepath=sourcepath, rel=rel)
            abs_path = self._path / remote
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(content)
            writes.append(remote)
        removes = []
        for rel in current:
            if rel in files:
                continue
            remote = to_remote(sourcepath=sourcepath, rel=rel)
            (self._path / remote).unlink(missing_ok=True)
            removes.append(remote)
        repo = Repo(str(self._path))
        try:
            if writes:
                porcelain.add(repo, paths=[str(self._path / p) for p in writes])
            if removes:
                porcelain.remove(repo, paths=[str(self._path / p) for p in removes])
            check_staged(sourcepath=sourcepath, paths=_staged_paths(repo))
        finally:
            repo.close()

    def commit(self, *, message: str, author: str) -> str | None:
        repo = Repo(str(self._path))
        try:
            index_tree = repo.open_index().commit(repo.object_store)
            try:
                if index_tree == repo[repo.head()].tree:
                    return None
            except KeyError:
                pass
            sha = porcelain.commit(
                repo,
                message=message.encode(),
                author=author.encode(),
                committer=author.encode(),
            )
            return sha.decode()
        finally:
            repo.close()

    def head_sha(self) -> str | None:
        repo = Repo(str(self._path))
        try:
            return repo.head().decode()
        except KeyError:
            return None
        finally:
            repo.close()

    def head_ref(self) -> str:
        repo = Repo(str(self._path))
        try:
            raw = repo.refs.read_ref(b"HEAD")
            if raw is not None and raw.startswith(b"ref: "):
                return raw[5:].decode()
            return "HEAD"
        finally:
            repo.close()

    def push(self, *, url: str, ref: str, username: str = "", password: str = "") -> str:
        repo = Repo(str(self._path))
        try:
            sha = repo.head().decode()
        finally:
            repo.close()
        try:
            porcelain.push(
                str(self._path),
                strip_credentials_in_url(url),
                refspecs=[f"HEAD:{ref}"],
                force=False,
                username=username or None,
                password=password or None,
            )
        except DivergedBranches as exc:
            raise GitPushError("non-fast-forward") from exc
        except Exception as exc:
            raise GitPushError(str(exc)) from exc
        return sha


def _clone(url: str, dest: Path, *, branch: str | None) -> None:
    """Clone `branch` when it exists; unborn remotes clone HEAD and point at `branch`."""
    try:
        porcelain.clone(url, str(dest), branch=branch.encode() if branch else None)
        return
    except ValueError as exc:
        if "is not a valid branch or tag" not in str(exc):
            raise
        if dest.exists():
            shutil.rmtree(dest)
        porcelain.clone(url, str(dest))
        if not branch:
            return
        repo = Repo(str(dest))
        try:
            repo.refs.set_symbolic_ref(b"HEAD", f"refs/heads/{branch}".encode())
        finally:
            repo.close()


def _staged_paths(repo: Repo) -> list[str]:
    index_tree = repo.open_index().commit(repo.object_store)
    try:
        head_tree = repo[repo.head()].tree
    except KeyError:
        head_tree = None
    paths: list[str] = []
    for change in tree_changes(repo.object_store, head_tree, index_tree):
        entry = change.old if change.type == CHANGE_DELETE else change.new
        if entry.path:
            paths.append(entry.path.decode())
    return paths
