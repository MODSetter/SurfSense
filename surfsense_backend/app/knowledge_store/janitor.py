"""Sweep abandoned working copies across every workspace."""

from __future__ import annotations

from app.knowledge_store.store import KnowledgeStore
from app.knowledge_store.store_path import working_copies_root

#: Far beyond any turn; a crashed turn's copy is recovered (committed) by the
#: thread's next turn well before this — only abandoned threads reach the TTL.
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60


async def prune_abandoned_working_copies(
    *, older_than_seconds: float = DEFAULT_MAX_AGE_SECONDS
) -> dict[str, list[str]]:
    """Prune copies older than the TTL in every workspace; pruned ids by workspace."""
    root = working_copies_root()
    if not root.is_dir():
        return {}
    pruned: dict[str, list[str]] = {}
    for workspace_dir in sorted(root.iterdir()):
        if not workspace_dir.is_dir():
            continue
        store = KnowledgeStore.for_workspace(workspace_dir.name)
        ids = await store.prune_working_copies(older_than_seconds=older_than_seconds)
        if ids:
            pruned[workspace_dir.name] = ids
    return pruned
