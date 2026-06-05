"""Resolve user-supplied paths to absolute paths the backends accept."""

from __future__ import annotations

import posixpath
from typing import TYPE_CHECKING

from langchain.tools import ToolRuntime

from app.agents.multi_agent_chat.shared.middleware.filesystem.backends.multi_root_local_folder import (
    MultiRootLocalFolderBackend,
)
from app.agents.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)
from app.agents.shared.filesystem_selection import FilesystemMode

from ..shared.paths import (
    extract_mount_from_path,
    local_parent_path,
    normalize_absolute_path,
)
from .mode import default_cwd

if TYPE_CHECKING:
    from .middleware import SurfSenseFilesystemMiddleware


def current_cwd(
    mw: SurfSenseFilesystemMiddleware,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
) -> str:
    cwd = runtime.state.get("cwd") if hasattr(runtime, "state") else None
    if isinstance(cwd, str) and cwd.startswith("/"):
        return cwd
    return default_cwd(mw._filesystem_mode)


def get_contract_suggested_path(
    mw: SurfSenseFilesystemMiddleware,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
) -> str:
    """Read the planner's suggested write path; otherwise default to ``notes.md``."""
    contract = runtime.state.get("file_operation_contract") or {}
    suggested = contract.get("suggested_path")
    if isinstance(suggested, str) and suggested.strip():
        return normalize_absolute_path(suggested)
    return default_cwd(mw._filesystem_mode).rstrip("/") + "/notes.md"


def resolve_relative(
    mw: SurfSenseFilesystemMiddleware,
    path: str,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
) -> str:
    """Resolve ``path`` against cwd (no-op if already absolute)."""
    candidate = path.strip()
    if not candidate:
        return current_cwd(mw, runtime)
    if candidate.startswith("/"):
        return normalize_absolute_path(candidate)
    cwd = current_cwd(mw, runtime)
    joined = posixpath.normpath(posixpath.join(cwd, candidate))
    return normalize_absolute_path(joined)


def resolve_write_target_path(
    mw: SurfSenseFilesystemMiddleware,
    file_path: str,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
) -> str:
    """Empty → contract suggestion; desktop → mount-prefix; cloud → cwd-relative."""
    candidate = file_path.strip()
    if not candidate:
        return get_contract_suggested_path(mw, runtime)
    if mw._filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
        return normalize_local_mount_path(mw, candidate, runtime)
    return resolve_relative(mw, candidate, runtime)


def resolve_move_target_path(
    mw: SurfSenseFilesystemMiddleware,
    file_path: str,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
) -> str:
    """Empty → empty (caller validates); desktop → mount-prefix; cloud → cwd-relative."""
    candidate = file_path.strip()
    if not candidate:
        return ""
    if mw._filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
        return normalize_local_mount_path(mw, candidate, runtime)
    return resolve_relative(mw, candidate, runtime)


def resolve_list_target_path(
    mw: SurfSenseFilesystemMiddleware,
    path: str,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
) -> str:
    """Root stays root; desktop → mount-prefix; cloud → cwd-relative."""
    candidate = path.strip() or current_cwd(mw, runtime)
    if candidate == "/":
        return "/"
    if mw._filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
        return normalize_local_mount_path(mw, candidate, runtime)
    return resolve_relative(mw, candidate, runtime)


def normalize_local_mount_path(
    mw: SurfSenseFilesystemMiddleware,
    candidate: str,
    runtime: ToolRuntime[None, SurfSenseFilesystemState],
) -> str:
    """Desktop only: prepend a mount prefix when the path doesn't already have one.

    Resolution order: explicit mount prefix → single available mount →
    contract-suggested mount → mount where the path exists → mount where the
    parent exists → backend default mount.
    """
    normalized = normalize_absolute_path(candidate)
    backend = mw._get_backend(runtime)
    if not isinstance(backend, MultiRootLocalFolderBackend):
        return normalized

    mounts = backend.list_mounts()
    explicit_mount = extract_mount_from_path(normalized, mounts)
    if explicit_mount:
        return normalized

    if len(mounts) == 1:
        return f"/{mounts[0]}{normalized}"

    suggested_mount: str | None = None
    contract = runtime.state.get("file_operation_contract") or {}
    suggested_path = contract.get("suggested_path")
    if isinstance(suggested_path, str) and suggested_path.strip():
        normalized_suggested = normalize_absolute_path(suggested_path)
        suggested_mount = extract_mount_from_path(normalized_suggested, mounts)

    matching_mounts = [
        mount
        for mount in mounts
        if _path_exists_under_mount(backend, mount, normalized)
    ]
    if len(matching_mounts) == 1:
        return f"/{matching_mounts[0]}{normalized}"

    parent_path = local_parent_path(normalized)
    if parent_path != "/":
        parent_matching_mounts = [
            mount
            for mount in mounts
            if _path_exists_under_mount(backend, mount, parent_path)
        ]
        if len(parent_matching_mounts) == 1:
            return f"/{parent_matching_mounts[0]}{normalized}"

    if suggested_mount:
        return f"/{suggested_mount}{normalized}"

    return f"/{backend.default_mount()}{normalized}"


def _path_exists_under_mount(
    backend: MultiRootLocalFolderBackend,
    mount: str,
    local_path: str,
) -> bool:
    result = backend.list_tree(
        f"/{mount}{local_path}",
        max_depth=0,
        page_size=1,
        include_files=True,
        include_dirs=True,
    )
    return not bool(result.get("error"))
