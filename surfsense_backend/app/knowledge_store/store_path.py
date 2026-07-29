"""On-disk location of a workspace's versioned store (single owner of the layout)."""

from __future__ import annotations

from pathlib import Path

from app.knowledge_store.settings import load_knowledge_store_settings


def workspace_store_path(workspace_id: int | str) -> Path:
    """Absolute directory holding a single workspace's versioned history."""
    root = load_knowledge_store_settings().root
    return Path(root) / str(workspace_id)


def stored_workspace_ids() -> list[int]:
    """Workspace ids that have a store on disk, ascending.

    The directory listing is the source: ``KNOWLEDGE_STORE_ENABLED`` is
    process-global rather than per-workspace, so nothing in the database says
    which workspaces have a repo. ``.working_copies`` sits alongside them and is
    excluded by the digit check.
    """
    root = Path(load_knowledge_store_settings().root)
    if not root.is_dir():
        return []
    return sorted(
        int(entry.name)
        for entry in root.iterdir()
        if entry.is_dir() and entry.name.isdigit()
    )


def working_copies_root() -> Path:
    """Absolute directory holding every workspace's working copies."""
    root = load_knowledge_store_settings().root
    return Path(root) / ".working_copies"


def workspace_working_copies_path(workspace_id: int | str) -> Path:
    """Absolute directory holding a workspace's private working copies."""
    return working_copies_root() / str(workspace_id)
