"""deepagents adapter: agent file ops on the turn's private working copy."""

from __future__ import annotations

from typing import Any

from deepagents.backends.protocol import (
    EditResult,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    WriteResult,
)
from langgraph.prebuilt.tool_node import ToolRuntime

from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.multi_root_local_folder import (
    MultiRootLocalFolderBackend,
)
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.service import thread_working_copy_id

__all__ = ["GitTreeBackend", "thread_working_copy_id"]

_DOCUMENTS_MOUNT = "documents"


class GitTreeBackend:
    """Serve ``/documents/...`` from the turn's private working copy.

    A thin mount over the knowledge store's working copy: opened lazily on the
    first operation, plain file ops for the rest of the turn. No staging, no
    state overlay; the end-of-turn commit reads the copy's diff.
    """

    def __init__(self, workspace_id: int | str, runtime: ToolRuntime) -> None:
        self.workspace_id = workspace_id
        self._runtime = runtime
        self._mounted: MultiRootLocalFolderBackend | None = None

    async def _backend(self) -> MultiRootLocalFolderBackend:
        if self._mounted is None:
            configurable = (self._runtime.config or {}).get("configurable") or {}
            store = KnowledgeStore.for_workspace(self.workspace_id)
            copy = await store.open_turn_copy(configurable.get("thread_id"))
            # Mount the copy's documents/ subtree, not its root: the repo keeps
            # the documents/ prefix (C1), so agent writes must land under it —
            # the same paths the editor recorder and the migration seeder use.
            documents_root = copy.path / _DOCUMENTS_MOUNT
            documents_root.mkdir(exist_ok=True)
            self._mounted = MultiRootLocalFolderBackend(
                ((_DOCUMENTS_MOUNT, str(documents_root)),)
            )
        return self._mounted

    async def als_info(self, path: str) -> list[FileInfo]:
        return await (await self._backend()).als_info(path)

    async def aread(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        return await (await self._backend()).aread(file_path, offset, limit)

    async def aread_raw(self, file_path: str) -> str:
        return await (await self._backend()).aread_raw(file_path)

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        return await (await self._backend()).awrite(file_path, content)

    async def aedit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        return await (await self._backend()).aedit(
            file_path, old_string, new_string, replace_all
        )

    async def aglob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        return await (await self._backend()).aglob_info(pattern, path)

    async def agrep_raw(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> list[GrepMatch] | str:
        return await (await self._backend()).agrep_raw(pattern, path, glob)

    async def alist_tree(
        self,
        path: str = "/",
        *,
        max_depth: int | None = 8,
        page_size: int = 500,
        include_files: bool = True,
        include_dirs: bool = True,
    ) -> dict[str, Any]:
        return await (await self._backend()).alist_tree(
            path,
            max_depth=max_depth,
            page_size=page_size,
            include_files=include_files,
            include_dirs=include_dirs,
        )

    async def amove(
        self,
        source_path: str,
        destination_path: str,
        overwrite: bool = False,
    ) -> WriteResult:
        return await (await self._backend()).amove(
            source_path, destination_path, overwrite
        )

    async def adelete_file(self, file_path: str) -> WriteResult:
        return await (await self._backend()).adelete_file(file_path)

    async def amkdir(
        self,
        dir_path: str,
        parents: bool = True,
        exist_ok: bool = True,
    ) -> WriteResult:
        # Git ignores empty directories, so an empty folder needs a .keep marker
        # to enter the turn's diff — the marker the facade's create_folder writes.
        # The dir must exist first for that marker write to resolve.
        backend = await self._backend()
        made = await backend.amkdir(dir_path, parents=parents, exist_ok=exist_ok)
        if made.error:
            return made
        return await backend.awrite(self._keep_marker(dir_path), "")

    async def armdir(self, dir_path: str) -> WriteResult:
        # A folder is removed by removing its .keep; refuse one that still holds
        # documents. An untracked folder has no marker, so a missing one succeeds.
        backend = await self._backend()
        keep = self._keep_marker(dir_path)
        for info in await backend.als_info(dir_path):
            path = (info.get("path") or "").rstrip("/")
            if path and path != keep:
                return WriteResult(
                    error=f"Error: directory '{dir_path}' is not empty. "
                    "Remove its contents first."
                )
        result = await backend.adelete_file(keep)
        return WriteResult(path=dir_path) if result.error else result

    @staticmethod
    def _keep_marker(dir_path: str) -> str:
        from app.knowledge_store.paths import KEEP_FILE

        return f"{dir_path.rstrip('/')}/{KEEP_FILE}"

    async def aupload_files(
        self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        return await (await self._backend()).aupload_files(files)

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return await (await self._backend()).adownload_files(paths)
