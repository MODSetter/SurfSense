"""On-disk location of a workspace's versioned store (single owner of the layout)."""

from __future__ import annotations

from pathlib import Path

from app.knowledge_store.settings import load_knowledge_store_settings


def workspace_store_path(workspace_id: int | str) -> Path:
    """Absolute directory holding a single workspace's versioned history."""
    root = load_knowledge_store_settings().root
    return Path(root) / str(workspace_id)
