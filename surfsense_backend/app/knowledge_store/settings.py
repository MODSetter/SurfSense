"""Knowledge-store enablement: process-wide config and per-workspace flip state.

The global ``KNOWLEDGE_STORE_ENABLED`` env is the master kill switch; each
workspace flips individually via ``workspaces.knowledge_store_enabled`` after
its migration seed passes parity. A workspace is git-native only when both
are on.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeStoreSettings:
    """Resolved knowledge-store configuration for the current process."""

    enabled: bool
    root: str


def load_knowledge_store_settings() -> KnowledgeStoreSettings:
    """Resolve knowledge-store settings from the central ``Config`` singleton."""
    from app.config import config

    return KnowledgeStoreSettings(
        enabled=config.KNOWLEDGE_STORE_ENABLED,
        root=config.KNOWLEDGE_STORE_ROOT,
    )


_FLAG_TTL_SECONDS = 30.0
# ponytail: in-process TTL cache, so a flip propagates within 30s per process;
# pub/sub invalidation is the upgrade if that window ever matters.
_flag_cache: dict[int, tuple[bool, float]] = {}


async def knowledge_store_enabled_for(workspace_id: int) -> bool:
    """Whether ``workspace_id`` is git-native right now.

    True only when the global master switch and the workspace's own flip
    flag are both on. The workspace flag is cached per process; the global
    switch is read live, so killing it takes effect immediately.
    """
    if not load_knowledge_store_settings().enabled:
        return False
    cached = _flag_cache.get(workspace_id)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    enabled = await _read_workspace_flag(workspace_id)
    _flag_cache[workspace_id] = (enabled, time.monotonic() + _FLAG_TTL_SECONDS)
    return enabled


async def _read_workspace_flag(workspace_id: int) -> bool:
    """``workspaces.knowledge_store_enabled`` for one row; False if absent."""
    from sqlalchemy import select

    from app.db import Workspace, async_session_maker

    async with async_session_maker() as session:
        return bool(
            await session.scalar(
                select(Workspace.knowledge_store_enabled).where(
                    Workspace.id == workspace_id
                )
            )
        )
