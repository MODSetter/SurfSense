"""Filesystem backend resolver for cloud and desktop-local modes."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from deepagents.backends.protocol import BackendProtocol
from deepagents.backends.state import StateBackend
from langgraph.prebuilt.tool_node import ToolRuntime

from app.agents.new_chat.filesystem_selection import FilesystemMode, FilesystemSelection
from app.agents.new_chat.middleware.kb_postgres_backend import KBPostgresBackend
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
    *,
    search_space_id: int | None = None,
) -> Callable[[ToolRuntime], BackendProtocol]:
    """Create deepagents backend resolver for the selected filesystem mode.

    In cloud mode the resolver returns a fresh :class:`KBPostgresBackend`
    bound to the current ``runtime`` so the backend can read staging state
    (``staged_dirs``, ``pending_moves``, ``files`` cache, ``kb_anon_doc``,
    ``kb_matched_chunk_ids``) for each tool call. When no ``search_space_id``
    is provided, the resolver falls back to :class:`StateBackend` (used by
    sub-agents and tests that don't need DB-backed reads).

    Desktop-local mode unchanged.
    """

    if selection.mode == FilesystemMode.DESKTOP_LOCAL_FOLDER and selection.local_mounts:

        def _resolve_local(_runtime: ToolRuntime) -> MultiRootLocalFolderBackend:
            mounts = tuple(
                (entry.mount_id, entry.root_path) for entry in selection.local_mounts
            )
            return _cached_multi_root_backend(mounts)

        return _resolve_local

    if search_space_id is not None:

        def _resolve_kb(runtime: ToolRuntime) -> BackendProtocol:
            return KBPostgresBackend(search_space_id, runtime)

        return _resolve_kb

    def _resolve_state(runtime: ToolRuntime) -> StateBackend:
        return StateBackend(runtime)

    return _resolve_state
