"""SurfSense filesystem middleware: class + focused-responsibility helpers."""

from __future__ import annotations

from .index import (
    SurfSenseFilesystemMiddleware,
    check_cloud_write_namespace,
    current_cwd,
    default_cwd,
    get_contract_suggested_path,
    is_cloud,
    normalize_local_mount_path,
    resolve_list_target_path,
    resolve_move_target_path,
    resolve_relative,
    resolve_write_target_path,
    run_async_blocking,
)

__all__ = [
    "SurfSenseFilesystemMiddleware",
    "check_cloud_write_namespace",
    "current_cwd",
    "default_cwd",
    "get_contract_suggested_path",
    "is_cloud",
    "normalize_local_mount_path",
    "resolve_list_target_path",
    "resolve_move_target_path",
    "resolve_relative",
    "resolve_write_target_path",
    "run_async_blocking",
]
