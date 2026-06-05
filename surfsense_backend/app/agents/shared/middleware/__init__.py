"""Shared middleware components for the SurfSense chat agents."""

from app.agents.shared.middleware.busy_mutex import BusyMutexMiddleware
from app.agents.shared.middleware.compaction import (
    SurfSenseCompactionMiddleware,
    create_surfsense_compaction_middleware,
)
from app.agents.shared.middleware.kb_persistence import (
    KnowledgeBasePersistenceMiddleware,
    commit_staged_filesystem_state,
)
from app.agents.shared.middleware.knowledge_search import (
    KnowledgePriorityMiddleware,
)
from app.agents.shared.middleware.memory_injection import (
    MemoryInjectionMiddleware,
)
from app.agents.shared.middleware.permission import PermissionMiddleware
from app.agents.shared.middleware.retry_after import RetryAfterMiddleware

__all__ = [
    "BusyMutexMiddleware",
    "KnowledgeBasePersistenceMiddleware",
    "KnowledgePriorityMiddleware",
    "MemoryInjectionMiddleware",
    "PermissionMiddleware",
    "RetryAfterMiddleware",
    "SurfSenseCompactionMiddleware",
    "commit_staged_filesystem_state",
    "create_surfsense_compaction_middleware",
]
