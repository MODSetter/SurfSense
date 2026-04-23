"""Filesystem backend resolver for cloud and desktop-local modes."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from deepagents.backends.state import StateBackend
from langgraph.prebuilt.tool_node import ToolRuntime

from app.agents.new_chat.filesystem_selection import FilesystemMode, FilesystemSelection
from app.agents.new_chat.middleware.local_folder_backend import LocalFolderBackend


@lru_cache(maxsize=64)
def _cached_local_backend(root_path: str) -> LocalFolderBackend:
    return LocalFolderBackend(root_path)


def build_backend_resolver(
    selection: FilesystemSelection,
) -> Callable[[ToolRuntime], StateBackend | LocalFolderBackend]:
    """Create deepagents backend resolver for the selected filesystem mode."""

    if (
        selection.mode == FilesystemMode.DESKTOP_LOCAL_FOLDER
        and selection.local_root_path is not None
    ):

        def _resolve_local(_runtime: ToolRuntime) -> LocalFolderBackend:
            return _cached_local_backend(selection.local_root_path or "")

        return _resolve_local

    def _resolve_cloud(runtime: ToolRuntime) -> StateBackend:
        return StateBackend(runtime)

    return _resolve_cloud
