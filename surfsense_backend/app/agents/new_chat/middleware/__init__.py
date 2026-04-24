"""Middleware components for the SurfSense new chat agent."""

from app.agents.new_chat.middleware.dedup_tool_calls import (
    DedupHITLToolCallsMiddleware,
)
from app.agents.new_chat.middleware.filesystem import (
    SurfSenseFilesystemMiddleware,
)
from app.agents.new_chat.middleware.file_intent import (
    FileIntentMiddleware,
)
from app.agents.new_chat.middleware.knowledge_search import (
    KnowledgeBaseSearchMiddleware,
)
from app.agents.new_chat.middleware.memory_injection import (
    MemoryInjectionMiddleware,
)

__all__ = [
    "DedupHITLToolCallsMiddleware",
    "FileIntentMiddleware",
    "KnowledgeBaseSearchMiddleware",
    "MemoryInjectionMiddleware",
    "SurfSenseFilesystemMiddleware",
]
