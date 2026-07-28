"""Git-native versioned storage for workspace knowledge."""

from __future__ import annotations

from app.knowledge_store.backends.content_store import Revision
from app.knowledge_store.store import KnowledgeStore
from app.knowledge_store.transaction import Transaction

__all__ = [
    "KnowledgeStore",
    "Revision",
    "Transaction",
]
