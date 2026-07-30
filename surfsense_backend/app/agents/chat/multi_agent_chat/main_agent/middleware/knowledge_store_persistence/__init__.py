"""Git-native end-of-turn persistence: one revision per agent turn."""

from .builder import build_knowledge_store_persistence_mw
from .commit_turn import commit_turn_working_copy
from .middleware import KnowledgeStorePersistenceMiddleware

__all__ = [
    "KnowledgeStorePersistenceMiddleware",
    "build_knowledge_store_persistence_mw",
    "commit_turn_working_copy",
]
