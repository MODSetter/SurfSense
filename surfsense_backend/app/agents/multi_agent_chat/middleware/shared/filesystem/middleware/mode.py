"""Mode-derived facts: ``is_cloud`` and ``default_cwd``."""

from __future__ import annotations

from app.agents.shared.filesystem_selection import FilesystemMode
from app.agents.new_chat.path_resolver import DOCUMENTS_ROOT


def is_cloud(mode: FilesystemMode) -> bool:
    return mode == FilesystemMode.CLOUD


def default_cwd(mode: FilesystemMode) -> str:
    """``/documents`` on cloud; ``/`` on desktop (mounts are children of ``/``)."""
    return DOCUMENTS_ROOT if is_cloud(mode) else "/"
