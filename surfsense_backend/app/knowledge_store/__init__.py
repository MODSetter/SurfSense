"""Git-native versioned storage for workspace knowledge."""

from __future__ import annotations

from app.knowledge_store.engines.base import (
    Change,
    Revision,
    TrackedPath,
    WorkingCopy,
)
from app.knowledge_store.store import KnowledgeStore
from app.knowledge_store.transaction import Transaction

__all__ = [
    "Change",
    "KnowledgeStore",
    "Revision",
    "TrackedPath",
    "Transaction",
    "WorkingCopy",
]
