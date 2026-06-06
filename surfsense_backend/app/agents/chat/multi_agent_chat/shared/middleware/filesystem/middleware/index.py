"""Public surface of the middleware package: class + helpers used by tool factories."""

from __future__ import annotations

from .async_dispatch import run_async_blocking
from .middleware import SurfSenseFilesystemMiddleware
from .mode import default_cwd, is_cloud
from .namespace_policy import check_cloud_write_namespace
from .path_resolution import (
    current_cwd,
    get_contract_suggested_path,
    normalize_local_mount_path,
    resolve_list_target_path,
    resolve_move_target_path,
    resolve_relative,
    resolve_write_target_path,
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
