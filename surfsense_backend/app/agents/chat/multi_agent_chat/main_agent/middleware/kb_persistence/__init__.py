"""End-of-turn KB persistence middleware (main-agent only)."""

from .builder import build_kb_persistence_mw
from .middleware import (
    KnowledgeBasePersistenceMiddleware,
    commit_staged_filesystem_state,
)

__all__ = [
    "KnowledgeBasePersistenceMiddleware",
    "build_kb_persistence_mw",
    "commit_staged_filesystem_state",
]
