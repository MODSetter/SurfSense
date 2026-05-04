"""Middleware components for the SurfSense new chat agent."""

from app.agents.new_chat.middleware.action_log import ActionLogMiddleware
from app.agents.new_chat.middleware.anonymous_document import (
    AnonymousDocumentMiddleware,
)
from app.agents.new_chat.middleware.busy_mutex import BusyMutexMiddleware
from app.agents.new_chat.middleware.compaction import (
    SurfSenseCompactionMiddleware,
    create_surfsense_compaction_middleware,
)
from app.agents.new_chat.middleware.context_editing import (
    ClearToolUsesEdit,
    SpillingContextEditingMiddleware,
    SpillToBackendEdit,
)
from app.agents.new_chat.middleware.dedup_tool_calls import (
    DedupHITLToolCallsMiddleware,
)
from app.agents.new_chat.middleware.doom_loop import DoomLoopMiddleware
from app.agents.new_chat.middleware.file_intent import (
    FileIntentMiddleware,
)
from app.agents.new_chat.middleware.filesystem import (
    SurfSenseFilesystemMiddleware,
)
from app.agents.new_chat.middleware.flatten_system import (
    FlattenSystemMessageMiddleware,
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
from app.agents.new_chat.middleware.noop_injection import NoopInjectionMiddleware
from app.agents.new_chat.middleware.otel_span import OtelSpanMiddleware
from app.agents.new_chat.middleware.permission import PermissionMiddleware
from app.agents.new_chat.middleware.retry_after import RetryAfterMiddleware
from app.agents.new_chat.middleware.skills_backends import (
    BuiltinSkillsBackend,
    SearchSpaceSkillsBackend,
    build_skills_backend_factory,
    default_skills_sources,
)
from app.agents.new_chat.middleware.tool_call_repair import (
    ToolCallNameRepairMiddleware,
)

__all__ = [
    "ActionLogMiddleware",
    "AnonymousDocumentMiddleware",
    "BuiltinSkillsBackend",
    "BusyMutexMiddleware",
    "ClearToolUsesEdit",
    "DedupHITLToolCallsMiddleware",
    "DoomLoopMiddleware",
    "FileIntentMiddleware",
    "FlattenSystemMessageMiddleware",
    "KnowledgeBasePersistenceMiddleware",
    "KnowledgeBaseSearchMiddleware",
    "KnowledgePriorityMiddleware",
    "KnowledgeTreeMiddleware",
    "MemoryInjectionMiddleware",
    "NoopInjectionMiddleware",
    "OtelSpanMiddleware",
    "PermissionMiddleware",
    "RetryAfterMiddleware",
    "SearchSpaceSkillsBackend",
    "SpillToBackendEdit",
    "SpillingContextEditingMiddleware",
    "SurfSenseCompactionMiddleware",
    "SurfSenseFilesystemMiddleware",
    "ToolCallNameRepairMiddleware",
    "build_skills_backend_factory",
    "commit_staged_filesystem_state",
    "create_surfsense_compaction_middleware",
    "default_skills_sources",
]
