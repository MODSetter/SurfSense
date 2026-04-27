"""Desktop local-folder filesystem backend for deepagents tools."""

from __future__ import annotations

import asyncio
import fnmatch
import os
import threading
from collections import deque
from contextlib import ExitStack
from pathlib import Path
from time import time
from typing import Any
from uuid import uuid4

from deepagents.backends.protocol import (
    EditResult,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    WriteResult,
)
from deepagents.backends.utils import (
    create_file_data,
    format_read_response,
    perform_string_replacement,
)

_INVALID_PATH = "invalid_path"
_FILE_NOT_FOUND = "file_not_found"
_IS_DIRECTORY = "is_directory"


class LocalFolderBackend:
    """Filesystem backend rooted to a single local folder."""

    def __init__(self, root_path: str) -> None:
        root = Path(root_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            msg = f"Local filesystem root does not exist or is not a directory: {root_path}"
            raise ValueError(msg)
        self._root = root
        self._locks: dict[str, threading.Lock] = {}
        self._locks_mu = threading.Lock()
        self._tree_sessions: dict[str, dict[str, Any]] = {}
        self._tree_sessions_ttl_s = 900

    def _lock_for(self, path: str) -> threading.Lock:
        with self._locks_mu:
            if path not in self._locks:
                self._locks[path] = threading.Lock()
            return self._locks[path]

    def _resolve_virtual(self, virtual_path: str, *, allow_root: bool = False) -> Path:
        if not virtual_path.startswith("/"):
            msg = f"Invalid path (must be absolute): {virtual_path}"
            raise ValueError(msg)
        rel = virtual_path.lstrip("/")
        candidate = self._root if rel == "" else (self._root / rel)
        resolved = candidate.resolve()
        if not allow_root and resolved == self._root:
            msg = "Path must refer to a file or child directory under root"
            raise ValueError(msg)
        if not resolved.is_relative_to(self._root):
            msg = f"Path escapes local filesystem root: {virtual_path}"
            raise ValueError(msg)
        return resolved

    @staticmethod
    def _to_virtual(path: Path, root: Path) -> str:
        rel = path.relative_to(root).as_posix()
        return "/" if rel == "." else f"/{rel}"

    def _write_text_atomic(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(content, encoding="utf-8")
        os.replace(temp_path, path)

    def _acquire_path_locks(self, *paths: str) -> ExitStack:
        ordered_paths = sorted(set(paths))
        stack = ExitStack()
        for path in ordered_paths:
            stack.enter_context(self._lock_for(path))
        return stack

    @staticmethod
    def _clamp_page_size(page_size: int) -> int:
        return max(1, min(page_size, 1000))

    def _prune_expired_tree_sessions(self) -> None:
        now = time()
        expired = [
            cursor
            for cursor, session in self._tree_sessions.items()
            if now - float(session.get("last_accessed_at", now)) > self._tree_sessions_ttl_s
        ]
        for cursor in expired:
            self._tree_sessions.pop(cursor, None)

    def _read_dir_entries(self, directory_path: str) -> list[dict[str, Any]]:
        directory = Path(directory_path)
        try:
            children = sorted(
                directory.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except OSError:
            return []

        entries: list[dict[str, Any]] = []
        for child in children:
            try:
                stat_result = child.stat()
            except OSError:
                continue
            entries.append(
                {
                    "path": self._to_virtual(child, self._root),
                    "is_dir": child.is_dir(),
                    "size": stat_result.st_size if child.is_file() else 0,
                    "modified_at": str(stat_result.st_mtime),
                    "absolute_path": str(child),
                }
            )
        return entries

    def ls_info(self, path: str) -> list[FileInfo]:
        try:
            target = self._resolve_virtual(path, allow_root=True)
        except ValueError:
            return []
        if not target.exists() or not target.is_dir():
            return []
        infos: list[FileInfo] = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            infos.append(
                FileInfo(
                    path=self._to_virtual(child, self._root),
                    is_dir=child.is_dir(),
                    size=child.stat().st_size if child.is_file() else 0,
                    modified_at=str(child.stat().st_mtime),
                )
            )
        return infos

    async def als_info(self, path: str) -> list[FileInfo]:
        return await asyncio.to_thread(self.ls_info, path)

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        try:
            path = self._resolve_virtual(file_path)
        except ValueError:
            return f"Error: Invalid path '{file_path}'"
        if not path.exists():
            return f"Error: File '{file_path}' not found"
        if not path.is_file():
            return f"Error: Path '{file_path}' is not a file"
        content = path.read_text(encoding="utf-8", errors="replace")
        file_data = create_file_data(content)
        return format_read_response(file_data, offset, limit)

    async def aread(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        return await asyncio.to_thread(self.read, file_path, offset, limit)

    def read_raw(self, file_path: str) -> str:
        """Read raw file text without line-number formatting."""
        try:
            path = self._resolve_virtual(file_path)
        except ValueError:
            return f"Error: Invalid path '{file_path}'"
        if not path.exists():
            return f"Error: File '{file_path}' not found"
        if not path.is_file():
            return f"Error: Path '{file_path}' is not a file"
        return path.read_text(encoding="utf-8", errors="replace")

    async def aread_raw(self, file_path: str) -> str:
        """Async variant of read_raw."""
        return await asyncio.to_thread(self.read_raw, file_path)

    def write(self, file_path: str, content: str) -> WriteResult:
        try:
            path = self._resolve_virtual(file_path)
        except ValueError:
            return WriteResult(error=f"Error: Invalid path '{file_path}'")
        lock = self._lock_for(file_path)
        with lock:
            if path.exists():
                return WriteResult(
                    error=(
                        f"Cannot write to {file_path} because it already exists. "
                        "Read and then make an edit, or write to a new path."
                    )
                )
            self._write_text_atomic(path, content)
        return WriteResult(path=file_path, files_update=None)

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        return await asyncio.to_thread(self.write, file_path, content)

    def list_tree(
        self,
        path: str = "/",
        *,
        max_depth: int | None = 8,
        page_size: int = 500,
        cursor: str | None = None,
        include_files: bool = True,
        include_dirs: bool = True,
    ) -> dict[str, Any]:
        self._prune_expired_tree_sessions()
        if not include_files and not include_dirs:
            return {
                "entries": [],
                "next_cursor": None,
                "has_more": False,
                "truncated": False,
            }

        normalized_depth = None if max_depth is None else max(0, int(max_depth))
        page_limit = self._clamp_page_size(int(page_size))
        now = time()

        if cursor:
            session = self._tree_sessions.get(cursor)
            if not session:
                return {"error": "Invalid or expired cursor"}
            if (
                session.get("path") != path
                or session.get("max_depth") != normalized_depth
                or session.get("include_files") != include_files
                or session.get("include_dirs") != include_dirs
            ):
                return {"error": "Cursor options do not match request options"}
            state = session
        else:
            try:
                start = self._resolve_virtual(path, allow_root=True)
            except ValueError:
                return {"error": f"Error: invalid path '{path}'"}
            if not start.exists():
                return {"error": f"Error: path '{path}' not found"}
            if start.is_file():
                stat_result = start.stat()
                if include_files:
                    return {
                        "entries": [
                            {
                                "path": self._to_virtual(start, self._root),
                                "is_dir": False,
                                "size": stat_result.st_size,
                                "modified_at": str(stat_result.st_mtime),
                                "depth": 0,
                            }
                        ],
                        "next_cursor": None,
                        "has_more": False,
                        "truncated": False,
                    }
                return {
                    "entries": [],
                    "next_cursor": None,
                    "has_more": False,
                    "truncated": False,
                }
            state = {
                "path": path,
                "max_depth": normalized_depth,
                "include_files": include_files,
                "include_dirs": include_dirs,
                "pending_dirs": deque([(str(start), 0)]),
                "active_dir": None,
                "active_depth": 0,
                "active_entries": [],
                "active_index": 0,
            }

        entries: list[dict[str, Any]] = []
        truncated = False
        while len(entries) < page_limit:
            active_entries = state.get("active_entries", [])
            active_index = int(state.get("active_index", 0))
            if active_index >= len(active_entries):
                pending_dirs = state.get("pending_dirs", [])
                if not pending_dirs:
                    state["active_entries"] = []
                    state["active_index"] = 0
                    break
                next_dir_path, next_depth = pending_dirs.popleft()
                state["active_dir"] = next_dir_path
                state["active_depth"] = next_depth
                state["active_entries"] = self._read_dir_entries(next_dir_path)
                state["active_index"] = 0
                active_entries = state["active_entries"]
                active_index = 0

            if active_index >= len(active_entries):
                continue

            item = active_entries[active_index]
            state["active_index"] = active_index + 1
            item_depth = int(state.get("active_depth", 0)) + 1
            if normalized_depth is not None and item_depth > normalized_depth:
                continue
            if item["is_dir"]:
                if normalized_depth is None or item_depth <= normalized_depth:
                    state["pending_dirs"].append((item["absolute_path"], item_depth))
                if include_dirs:
                    entries.append(
                        {
                            "path": item["path"],
                            "is_dir": True,
                            "size": 0,
                            "modified_at": item["modified_at"],
                            "depth": item_depth,
                        }
                    )
            elif include_files:
                entries.append(
                    {
                        "path": item["path"],
                        "is_dir": False,
                        "size": item["size"],
                        "modified_at": item["modified_at"],
                        "depth": item_depth,
                    }
                )

            if len(entries) >= page_limit:
                truncated = True
                break

        has_more = bool(state.get("pending_dirs")) or (
            int(state.get("active_index", 0)) < len(state.get("active_entries", []))
        )
        if has_more:
            next_cursor = cursor or uuid4().hex
            state["last_accessed_at"] = now
            self._tree_sessions[next_cursor] = state
        else:
            next_cursor = None
            if cursor:
                self._tree_sessions.pop(cursor, None)

        return {
            "entries": entries,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "truncated": truncated,
        }

    async def alist_tree(
        self,
        path: str = "/",
        *,
        max_depth: int | None = 8,
        page_size: int = 500,
        cursor: str | None = None,
        include_files: bool = True,
        include_dirs: bool = True,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self.list_tree,
            path,
            max_depth=max_depth,
            page_size=page_size,
            cursor=cursor,
            include_files=include_files,
            include_dirs=include_dirs,
        )

    def move(
        self,
        source_path: str,
        destination_path: str,
        overwrite: bool = False,
    ) -> WriteResult:
        try:
            source = self._resolve_virtual(source_path)
            destination = self._resolve_virtual(destination_path)
        except ValueError:
            return WriteResult(
                error=(
                    f"Error: invalid source '{source_path}' or destination "
                    f"'{destination_path}' path"
                )
            )
        if source == destination:
            return WriteResult(error="Error: source and destination paths are the same")
        with self._acquire_path_locks(source_path, destination_path):
            if not source.exists():
                return WriteResult(error=f"Error: source path '{source_path}' not found")
            if destination.exists():
                if not overwrite:
                    return WriteResult(
                        error=(
                            f"Error: destination path '{destination_path}' already exists. "
                            "Set overwrite=True to replace files."
                        )
                    )
                if source.is_dir() or destination.is_dir():
                    return WriteResult(
                        error=(
                            "Error: overwrite=True is only supported for file-to-file moves."
                        )
                    )
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                if overwrite:
                    os.replace(source, destination)
                else:
                    source.rename(destination)
            except OSError as exc:
                return WriteResult(error=f"Error: failed to move '{source_path}': {exc}")
        return WriteResult(path=self._to_virtual(destination, self._root), files_update=None)

    async def amove(
        self,
        source_path: str,
        destination_path: str,
        overwrite: bool = False,
    ) -> WriteResult:
        return await asyncio.to_thread(
            self.move, source_path, destination_path, overwrite
        )

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        try:
            path = self._resolve_virtual(file_path)
        except ValueError:
            return EditResult(error=f"Error: Invalid path '{file_path}'")
        lock = self._lock_for(file_path)
        with lock:
            if not path.exists() or not path.is_file():
                return EditResult(error=f"Error: File '{file_path}' not found")
            content = path.read_text(encoding="utf-8", errors="replace")
            result = perform_string_replacement(content, old_string, new_string, replace_all)
            if isinstance(result, str):
                return EditResult(error=result)
            updated_content, occurrences = result
            self._write_text_atomic(path, updated_content)
        return EditResult(path=file_path, files_update=None, occurrences=int(occurrences))

    async def aedit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        return await asyncio.to_thread(
            self.edit, file_path, old_string, new_string, replace_all
        )

    def glob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        try:
            base = self._resolve_virtual(path, allow_root=True)
        except ValueError:
            return []

        if pattern.startswith("/"):
            search_base = self._root
            normalized_pattern = pattern.lstrip("/")
        else:
            search_base = base
            normalized_pattern = pattern

        matches: list[FileInfo] = []
        for hit in search_base.glob(normalized_pattern):
            try:
                resolved = hit.resolve()
                if not resolved.is_relative_to(self._root):
                    continue
            except Exception:
                continue
            matches.append(
                FileInfo(
                    path=self._to_virtual(resolved, self._root),
                    is_dir=resolved.is_dir(),
                    size=resolved.stat().st_size if resolved.is_file() else 0,
                    modified_at=str(resolved.stat().st_mtime),
                )
            )
        return matches

    async def aglob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        return await asyncio.to_thread(self.glob_info, pattern, path)

    def _iter_candidate_files(self, path: str | None, glob: str | None) -> list[Path]:
        base_virtual = path or "/"
        try:
            base = self._resolve_virtual(base_virtual, allow_root=True)
        except ValueError:
            return []
        if not base.exists():
            return []

        candidates = [p for p in base.rglob("*") if p.is_file()]
        if glob:
            candidates = [
                p
                for p in candidates
                if fnmatch.fnmatch(self._to_virtual(p, self._root), glob)
                or fnmatch.fnmatch(p.name, glob)
            ]
        return candidates

    def grep_raw(
        self, pattern: str, path: str | None = None, glob: str | None = None
    ) -> list[GrepMatch] | str:
        if not pattern:
            return "Error: pattern cannot be empty"
        matches: list[GrepMatch] = []
        for file_path in self._iter_candidate_files(path, glob):
            try:
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for idx, line in enumerate(lines, start=1):
                if pattern in line:
                    matches.append(
                        GrepMatch(
                            path=self._to_virtual(file_path, self._root),
                            line=idx,
                            text=line,
                        )
                    )
        return matches

    async def agrep_raw(
        self, pattern: str, path: str | None = None, glob: str | None = None
    ) -> list[GrepMatch] | str:
        return await asyncio.to_thread(self.grep_raw, pattern, path, glob)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses: list[FileUploadResponse] = []
        for virtual_path, content in files:
            try:
                target = self._resolve_virtual(virtual_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                temp_path = target.with_suffix(f"{target.suffix}.tmp")
                temp_path.write_bytes(content)
                os.replace(temp_path, target)
                responses.append(FileUploadResponse(path=virtual_path, error=None))
            except FileNotFoundError:
                responses.append(
                    FileUploadResponse(path=virtual_path, error=_FILE_NOT_FOUND)
                )
            except IsADirectoryError:
                responses.append(FileUploadResponse(path=virtual_path, error=_IS_DIRECTORY))
            except Exception:
                responses.append(FileUploadResponse(path=virtual_path, error=_INVALID_PATH))
        return responses

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        return await asyncio.to_thread(self.upload_files, files)

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for virtual_path in paths:
            try:
                target = self._resolve_virtual(virtual_path)
                if not target.exists():
                    responses.append(
                        FileDownloadResponse(
                            path=virtual_path, content=None, error=_FILE_NOT_FOUND
                        )
                    )
                    continue
                if target.is_dir():
                    responses.append(
                        FileDownloadResponse(
                            path=virtual_path, content=None, error=_IS_DIRECTORY
                        )
                    )
                    continue
                responses.append(
                    FileDownloadResponse(
                        path=virtual_path, content=target.read_bytes(), error=None
                    )
                )
            except Exception:
                responses.append(
                    FileDownloadResponse(path=virtual_path, content=None, error=_INVALID_PATH)
                )
        return responses

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return await asyncio.to_thread(self.download_files, paths)
