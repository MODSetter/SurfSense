"""Configuration for the knowledge-store module, sourced from the central Config."""

from __future__ import annotations

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
