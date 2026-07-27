"""Where a workspace's versioned store lives on disk.

Isolated so the on-disk layout has one owner: callers ask for a workspace's
store by id and never assemble paths themselves.
"""

from __future__ import annotations

from pathlib import Path

from app.knowledge_store.settings import load_knowledge_store_settings


def workspace_store_path(workspace_id: int | str) -> Path:
    """Absolute directory holding a single workspace's versioned history."""
    root = load_knowledge_store_settings().root
    return Path(root) / str(workspace_id)
