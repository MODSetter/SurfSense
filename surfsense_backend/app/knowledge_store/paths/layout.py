"""On-disk layout: where a workspace's git repo and working copies live.

Stays free of ``app.db`` at module load because the enqueue path imports it.
"""

from __future__ import annotations

from pathlib import Path

from app.knowledge_store.settings import load_knowledge_store_settings

_WORKING_COPIES_DIRNAME = ".working_copies"


def workspace_store_path(workspace_id: int | str) -> Path:
    """Absolute directory holding a single workspace's versioned history."""
    root = load_knowledge_store_settings().root
    return Path(root) / str(workspace_id)


def working_copies_root() -> Path:
    """Absolute directory holding every workspace's working copies."""
    root = load_knowledge_store_settings().root
    return Path(root) / _WORKING_COPIES_DIRNAME


def workspace_working_copies_path(workspace_id: int | str) -> Path:
    """Absolute directory holding a workspace's private working copies."""
    return working_copies_root() / str(workspace_id)
