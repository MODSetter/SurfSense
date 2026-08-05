"""Bind a workspace to its storage engine: the one place the engine is chosen."""

from __future__ import annotations

from app.knowledge_store.engines.base import VersionedContentEngine
from app.knowledge_store.engines.git import GitContentEngine
from app.knowledge_store.paths import (
    workspace_store_path,
    workspace_working_copies_path,
)


def build_engine(workspace_id: int | str) -> VersionedContentEngine:
    """The git engine over a workspace's repo and working copies."""
    return GitContentEngine(
        workspace_store_path(workspace_id),
        workspace_working_copies_path(workspace_id),
    )
