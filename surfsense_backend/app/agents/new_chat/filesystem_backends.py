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
    root_paths: tuple[str, ...],
) -> MultiRootLocalFolderBackend:
    return MultiRootLocalFolderBackend(root_paths)


def build_backend_resolver(
    selection: FilesystemSelection,
) -> Callable[[ToolRuntime], StateBackend | MultiRootLocalFolderBackend]:
    """Create deepagents backend resolver for the selected filesystem mode."""

    if selection.mode == FilesystemMode.DESKTOP_LOCAL_FOLDER and selection.local_root_paths:

        def _resolve_local(_runtime: ToolRuntime) -> MultiRootLocalFolderBackend:
            return _cached_multi_root_backend(selection.local_root_paths)

        return _resolve_local

    def _resolve_cloud(runtime: ToolRuntime) -> StateBackend:
        return StateBackend(runtime)

    return _resolve_cloud
