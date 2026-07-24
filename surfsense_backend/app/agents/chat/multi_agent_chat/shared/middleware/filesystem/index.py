"""Public composition factory for the filesystem middleware."""

from __future__ import annotations

from typing import Any

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode

from .middleware import SurfSenseFilesystemMiddleware


def build_filesystem_mw(
    *,
    backend_resolver: Any,
    filesystem_mode: FilesystemMode,
    workspace_id: int,
    user_id: str | None,
    thread_id: int | None,
    read_only: bool = False,
) -> SurfSenseFilesystemMiddleware:
    return SurfSenseFilesystemMiddleware(
        backend=backend_resolver,
        filesystem_mode=filesystem_mode,
        workspace_id=workspace_id,
        created_by_id=user_id,
        thread_id=thread_id,
        read_only=read_only,
    )
