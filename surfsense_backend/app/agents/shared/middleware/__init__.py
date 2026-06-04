"""Middleware components for the SurfSense new chat agent."""

from app.agents.shared.middleware.action_log import (
    ActionLogMiddleware,
    ToolDefinition,
)
from app.agents.shared.middleware.anonymous_document import (
    AnonymousDocumentMiddleware,
)
from app.agents.shared.middleware.busy_mutex import BusyMutexMiddleware
from app.agents.shared.middleware.compaction import (
    SurfSenseCompactionMiddleware,
    create_surfsense_compaction_middleware,
)
from app.agents.shared.middleware.context_editing import (
    ClearToolUsesEdit,
    SpillingContextEditingMiddleware,
    SpillToBackendEdit,
)
from app.agents.shared.middleware.dedup_tool_calls import (
    DedupHITLToolCallsMiddleware,
)
from app.agents.shared.middleware.doom_loop import DoomLoopMiddleware
from app.agents.shared.middleware.file_intent import (
    FileIntentMiddleware,
)
from app.agents.shared.middleware.flatten_system import (
    FlattenSystemMessageMiddleware,
)
from app.agents.shared.middleware.kb_persistence import (
    KnowledgeBasePersistenceMiddleware,
    commit_staged_filesystem_state,
)
from app.agents.shared.middleware.knowledge_search import (
    KnowledgeBaseSearchMiddleware,
    KnowledgePriorityMiddleware,
)
from app.agents.shared.middleware.knowledge_tree import (
    KnowledgeTreeMiddleware,
)
from app.agents.shared.middleware.memory_injection import (
    MemoryInjectionMiddleware,
)
from app.agents.shared.middleware.noop_injection import NoopInjectionMiddleware
from app.agents.shared.middleware.otel_span import OtelSpanMiddleware
from app.agents.shared.middleware.permission import PermissionMiddleware
from app.agents.shared.middleware.retry_after import RetryAfterMiddleware
from app.agents.shared.middleware.skills_backends import (
    BuiltinSkillsBackend,
    SearchSpaceSkillsBackend,
    build_skills_backend_factory,
    default_skills_sources,
)
from app.agents.shared.middleware.tool_call_repair import (
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
    "ToolCallNameRepairMiddleware",
    "ToolDefinition",
    "build_skills_backend_factory",
    "commit_staged_filesystem_state",
    "create_surfsense_compaction_middleware",
    "default_skills_sources",
]
