"""Git-native versioned storage for workspace knowledge.

Public surface: build a :class:`KnowledgeStore` for a workspace and read/commit
its history through it. Git is an implementation detail behind the facade.
"""

from __future__ import annotations

from app.knowledge_store.backends.base import StoredRevision
from app.knowledge_store.service import KnowledgeStore, RevisionDraft

__all__ = [
    "KnowledgeStore",
    "RevisionDraft",
    "StoredRevision",
]
