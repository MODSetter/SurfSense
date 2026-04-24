"""Aggregate multiple LocalFolderBackend roots behind mount-prefixed virtual paths."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from deepagents.backends.protocol import (
    EditResult,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    WriteResult,
)

from app.agents.new_chat.middleware.local_folder_backend import LocalFolderBackend

_INVALID_PATH = "invalid_path"
_FILE_NOT_FOUND = "file_not_found"
_IS_DIRECTORY = "is_directory"


class MultiRootLocalFolderBackend:
    """Route filesystem operations to one of several mounted local roots.

    Virtual paths are namespaced as:
    - `/<mount>/...`
    where `<mount>` is derived from each selected root folder name.
    """

    def __init__(self, mounts: tuple[tuple[str, str], ...]) -> None:
        if not mounts:
            msg = "At least one local mount is required"
            raise ValueError(msg)
        self._mount_to_backend: dict[str, LocalFolderBackend] = {}
        for raw_mount, raw_root in mounts:
            mount = raw_mount.strip()
            if not mount:
                msg = "Mount id cannot be empty"
                raise ValueError(msg)
            if mount in self._mount_to_backend:
                msg = f"Duplicate mount id: {mount}"
                raise ValueError(msg)
            normalized_root = str(Path(raw_root).expanduser().resolve())
            self._mount_to_backend[mount] = LocalFolderBackend(normalized_root)
        self._mount_order = tuple(self._mount_to_backend.keys())

    def list_mounts(self) -> tuple[str, ...]:
        return self._mount_order

    def default_mount(self) -> str:
        return self._mount_order[0]

    def _mount_error(self) -> str:
        mounts = ", ".join(f"/{mount}" for mount in self._mount_order)
        return (
            "Path must start with one of the selected folders: "
            f"{mounts}. Example: /{self._mount_order[0]}/file.txt"
        )

    def _split_mount_path(self, virtual_path: str) -> tuple[str, str]:
        if not virtual_path.startswith("/"):
            msg = f"Invalid path (must be absolute): {virtual_path}"
            raise ValueError(msg)
        rel = virtual_path.lstrip("/")
        if not rel:
            raise ValueError(self._mount_error())
        mount, _, remainder = rel.partition("/")
        backend = self._mount_to_backend.get(mount)
        if backend is None:
            raise ValueError(self._mount_error())
        local_path = f"/{remainder}" if remainder else "/"
        return mount, local_path

    @staticmethod
    def _prefix_mount_path(mount: str, local_path: str) -> str:
        if local_path == "/":
            return f"/{mount}"
        return f"/{mount}{local_path}"

    @staticmethod
    def _get_value(item: Any, key: str) -> Any:
        if isinstance(item, dict):
            return item.get(key)
        return getattr(item, key, None)

    @classmethod
    def _get_str(cls, item: Any, key: str) -> str:
        value = cls._get_value(item, key)
        return value if isinstance(value, str) else ""

    @classmethod
    def _get_int(cls, item: Any, key: str) -> int:
        value = cls._get_value(item, key)
        return int(value) if isinstance(value, int | float) else 0

    @classmethod
    def _get_bool(cls, item: Any, key: str) -> bool:
        value = cls._get_value(item, key)
        return bool(value)

    def _list_mount_roots(self) -> list[FileInfo]:
        return [
            FileInfo(path=f"/{mount}", is_dir=True, size=0, modified_at="0")
            for mount in self._mount_order
        ]

    def _transform_infos(self, mount: str, infos: list[FileInfo]) -> list[FileInfo]:
        transformed: list[FileInfo] = []
        for info in infos:
            transformed.append(
                FileInfo(
                    path=self._prefix_mount_path(mount, self._get_str(info, "path")),
                    is_dir=self._get_bool(info, "is_dir"),
                    size=self._get_int(info, "size"),
                    modified_at=self._get_str(info, "modified_at"),
                )
            )
        return transformed

    def ls_info(self, path: str) -> list[FileInfo]:
        if path == "/":
            return self._list_mount_roots()
        try:
            mount, local_path = self._split_mount_path(path)
        except ValueError:
            return []
        return self._transform_infos(mount, self._mount_to_backend[mount].ls_info(local_path))

    async def als_info(self, path: str) -> list[FileInfo]:
        return await asyncio.to_thread(self.ls_info, path)

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        try:
            mount, local_path = self._split_mount_path(file_path)
        except ValueError as exc:
            return f"Error: {exc}"
        return self._mount_to_backend[mount].read(local_path, offset, limit)

    async def aread(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        return await asyncio.to_thread(self.read, file_path, offset, limit)

    def read_raw(self, file_path: str) -> str:
        try:
            mount, local_path = self._split_mount_path(file_path)
        except ValueError as exc:
            return f"Error: {exc}"
        return self._mount_to_backend[mount].read_raw(local_path)

    async def aread_raw(self, file_path: str) -> str:
        return await asyncio.to_thread(self.read_raw, file_path)

    def write(self, file_path: str, content: str) -> WriteResult:
        try:
            mount, local_path = self._split_mount_path(file_path)
        except ValueError as exc:
            return WriteResult(error=f"Error: {exc}")
        result = self._mount_to_backend[mount].write(local_path, content)
        if result.path:
            result.path = self._prefix_mount_path(mount, result.path)
        return result

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
            mount, local_path = self._split_mount_path(file_path)
        except ValueError as exc:
            return EditResult(error=f"Error: {exc}")
        result = self._mount_to_backend[mount].edit(
            local_path, old_string, new_string, replace_all
        )
        if result.path:
            result.path = self._prefix_mount_path(mount, result.path)
        return result

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
        if path == "/":
            prefixed_results: list[FileInfo] = []
            if pattern.startswith("/"):
                mount, _, remainder = pattern.lstrip("/").partition("/")
                backend = self._mount_to_backend.get(mount)
                if not backend:
                    return []
                local_pattern = f"/{remainder}" if remainder else "/"
                return self._transform_infos(
                    mount, backend.glob_info(local_pattern, path="/")
                )
            for mount, backend in self._mount_to_backend.items():
                prefixed_results.extend(
                    self._transform_infos(mount, backend.glob_info(pattern, path="/"))
                )
            return prefixed_results

        try:
            mount, local_path = self._split_mount_path(path)
        except ValueError:
            return []
        return self._transform_infos(
            mount, self._mount_to_backend[mount].glob_info(pattern, path=local_path)
        )

    async def aglob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        return await asyncio.to_thread(self.glob_info, pattern, path)

    def grep_raw(
        self, pattern: str, path: str | None = None, glob: str | None = None
    ) -> list[GrepMatch] | str:
        if not pattern:
            return "Error: pattern cannot be empty"
        if path is None or path == "/":
            all_matches: list[GrepMatch] = []
            for mount, backend in self._mount_to_backend.items():
                result = backend.grep_raw(pattern, path="/", glob=glob)
                if isinstance(result, str):
                    return result
                all_matches.extend(
                    [
                        GrepMatch(
                            path=self._prefix_mount_path(mount, self._get_str(match, "path")),
                            line=self._get_int(match, "line"),
                            text=self._get_str(match, "text"),
                        )
                        for match in result
                    ]
                )
            return all_matches
        try:
            mount, local_path = self._split_mount_path(path)
        except ValueError as exc:
            return f"Error: {exc}"

        result = self._mount_to_backend[mount].grep_raw(
            pattern, path=local_path, glob=glob
        )
        if isinstance(result, str):
            return result
        return [
            GrepMatch(
                path=self._prefix_mount_path(mount, self._get_str(match, "path")),
                line=self._get_int(match, "line"),
                text=self._get_str(match, "text"),
            )
            for match in result
        ]

    async def agrep_raw(
        self, pattern: str, path: str | None = None, glob: str | None = None
    ) -> list[GrepMatch] | str:
        return await asyncio.to_thread(self.grep_raw, pattern, path, glob)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        grouped: dict[str, list[tuple[str, bytes]]] = {}
        invalid: list[FileUploadResponse] = []
        for virtual_path, content in files:
            try:
                mount, local_path = self._split_mount_path(virtual_path)
            except ValueError:
                invalid.append(FileUploadResponse(path=virtual_path, error=_INVALID_PATH))
                continue
            grouped.setdefault(mount, []).append((local_path, content))

        responses = list(invalid)
        for mount, mount_files in grouped.items():
            result = self._mount_to_backend[mount].upload_files(mount_files)
            responses.extend(
                [
                    FileUploadResponse(
                        path=self._prefix_mount_path(mount, self._get_str(item, "path")),
                        error=self._get_str(item, "error") or None,
                    )
                    for item in result
                ]
            )
        return responses

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        return await asyncio.to_thread(self.upload_files, files)

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        grouped: dict[str, list[str]] = {}
        invalid: list[FileDownloadResponse] = []
        for virtual_path in paths:
            try:
                mount, local_path = self._split_mount_path(virtual_path)
            except ValueError:
                invalid.append(
                    FileDownloadResponse(path=virtual_path, content=None, error=_INVALID_PATH)
                )
                continue
            grouped.setdefault(mount, []).append(local_path)

        responses = list(invalid)
        for mount, mount_paths in grouped.items():
            result = self._mount_to_backend[mount].download_files(mount_paths)
            responses.extend(
                [
                    FileDownloadResponse(
                        path=self._prefix_mount_path(mount, self._get_str(item, "path")),
                        content=self._get_value(item, "content"),
                        error=self._get_str(item, "error") or None,
                    )
                    for item in result
                ]
            )
        return responses

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return await asyncio.to_thread(self.download_files, paths)
