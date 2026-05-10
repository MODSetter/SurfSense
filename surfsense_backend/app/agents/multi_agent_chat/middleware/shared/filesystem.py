"""SurfSense filesystem tools/middleware."""

from __future__ import annotations

from typing import Any

from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware import SurfSenseFilesystemMiddleware


def build_filesystem_mw(
    *,
    backend_resolver: Any,
    filesystem_mode: FilesystemMode,
    search_space_id: int,
    user_id: str | None,
    thread_id: int | None,
) -> SurfSenseFilesystemMiddleware:
    return SurfSenseFilesystemMiddleware(
        backend=backend_resolver,
        filesystem_mode=filesystem_mode,
        search_space_id=search_space_id,
        created_by_id=user_id,
        thread_id=thread_id,
    )
