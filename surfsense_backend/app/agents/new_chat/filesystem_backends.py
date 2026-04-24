"""Filesystem backend resolver for cloud and desktop-local modes."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from deepagents.backends.state import StateBackend
from langgraph.prebuilt.tool_node import ToolRuntime

from app.agents.new_chat.filesystem_selection import FilesystemMode, FilesystemSelection
from app.agents.new_chat.middleware.multi_root_local_folder_backend import (
    MultiRootLocalFolderBackend,
)


@lru_cache(maxsize=64)
def _cached_multi_root_backend(
    mounts: tuple[tuple[str, str], ...],
) -> MultiRootLocalFolderBackend:
    return MultiRootLocalFolderBackend(mounts)


def build_backend_resolver(
    selection: FilesystemSelection,
) -> Callable[[ToolRuntime], StateBackend | MultiRootLocalFolderBackend]:
    """Create deepagents backend resolver for the selected filesystem mode."""

    if selection.mode == FilesystemMode.DESKTOP_LOCAL_FOLDER and selection.local_mounts:

        def _resolve_local(_runtime: ToolRuntime) -> MultiRootLocalFolderBackend:
            mounts = tuple(
                (entry.mount_id, entry.root_path) for entry in selection.local_mounts
            )
            return _cached_multi_root_backend(mounts)

        return _resolve_local

    def _resolve_cloud(runtime: ToolRuntime) -> StateBackend:
        return StateBackend(runtime)

    return _resolve_cloud
