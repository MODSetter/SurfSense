"""Middleware components for the SurfSense new chat agent."""

from app.agents.new_chat.middleware.dedup_tool_calls import (
    DedupHITLToolCallsMiddleware,
)
from app.agents.new_chat.middleware.filesystem import (
    SurfSenseFilesystemMiddleware,
)
from app.agents.new_chat.middleware.knowledge_search import (
    KnowledgeBaseSearchMiddleware,
)

__all__ = [
    "DedupHITLToolCallsMiddleware",
    "KnowledgeBaseSearchMiddleware",
    "SurfSenseFilesystemMiddleware",
]
