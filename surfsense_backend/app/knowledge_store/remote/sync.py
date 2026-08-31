"""First-sync apply and the later 3-way mirror."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.knowledge_store.identities import AGENT_IDENTITY
from app.knowledge_store.remote.paths import rel_from_local, to_local
from app.knowledge_store.remote.planner import FileChange

if TYPE_CHECKING:
    from app.knowledge_store import KnowledgeStore


async def apply_from_remote(
    store: KnowledgeStore, *, mount: str, files: dict[str, bytes]
) -> None:
    """Replace markdown under ``mount`` with ``files`` (rel → bytes)."""
    async with store.transaction(
        message="sync from remote", author=AGENT_IDENTITY
    ) as tx:
        for rel, content in files.items():
            tx.write(to_local(mount=mount, rel=rel), content)


async def apply_changes(
    store: KnowledgeStore, *, mount: str, changes: tuple[FileChange, ...]
) -> None:
    async with store.transaction(
        message="sync from remote", author=AGENT_IDENTITY
    ) as tx:
        for change in changes:
            path = to_local(mount=mount, rel=change.path)
            if change.content is None:
                tx.remove(path)
            else:
                tx.write(path, change.content)


async def md_under_mount(
    store: KnowledgeStore, mount: str, *, revision: str | None = None
) -> dict[str, bytes]:
    head = revision if revision is not None else await store.head()
    if head is None:
        return {}
    found: dict[str, bytes] = {}
    prefix = f"{mount}/"
    for tracked in await store.list_paths(head):
        path = tracked.path
        if path.startswith(prefix) and path.endswith(".md"):
            found[rel_from_local(mount=mount, path=path)] = await store.read_as_of(
                head, path
            )
    return found
