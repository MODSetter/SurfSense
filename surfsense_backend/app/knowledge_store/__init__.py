"""Git-native versioned storage for workspace knowledge."""

from __future__ import annotations

from app.knowledge_store.backends.base import StoredRevision
from app.knowledge_store.revision_draft import RevisionDraft
from app.knowledge_store.store import KnowledgeStore

__all__ = [
    "KnowledgeStore",
    "RevisionDraft",
    "StoredRevision",
]
