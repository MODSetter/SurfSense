"""Middleware components for the SurfSense new chat agent."""

from app.agents.new_chat.middleware.anonymous_document import (
    AnonymousDocumentMiddleware,
)
from app.agents.new_chat.middleware.dedup_tool_calls import (
    DedupHITLToolCallsMiddleware,
)
from app.agents.new_chat.middleware.file_intent import (
    FileIntentMiddleware,
)
from app.agents.new_chat.middleware.filesystem import (
    SurfSenseFilesystemMiddleware,
)
from app.agents.new_chat.middleware.kb_persistence import (
    KnowledgeBasePersistenceMiddleware,
    commit_staged_filesystem_state,
)
from app.agents.new_chat.middleware.knowledge_search import (
    KnowledgeBaseSearchMiddleware,
    KnowledgePriorityMiddleware,
)
from app.agents.new_chat.middleware.knowledge_tree import (
    KnowledgeTreeMiddleware,
)
from app.agents.new_chat.middleware.memory_injection import (
    MemoryInjectionMiddleware,
)

__all__ = [
    "AnonymousDocumentMiddleware",
    "DedupHITLToolCallsMiddleware",
    "FileIntentMiddleware",
    "KnowledgeBasePersistenceMiddleware",
    "KnowledgeBaseSearchMiddleware",
    "KnowledgePriorityMiddleware",
    "KnowledgeTreeMiddleware",
    "MemoryInjectionMiddleware",
    "SurfSenseFilesystemMiddleware",
    "commit_staged_filesystem_state",
]
