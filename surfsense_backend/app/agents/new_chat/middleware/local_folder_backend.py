"""Desktop local-folder filesystem backend for deepagents tools."""

from __future__ import annotations

import asyncio
import fnmatch
import os
import threading
from pathlib import Path

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
