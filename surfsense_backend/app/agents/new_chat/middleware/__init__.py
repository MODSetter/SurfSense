"""Backward-compatible shim package.

The agent middleware now lives in the shared kernel at
``app.agents.shared.middleware``. This package re-exports it so frozen
single-agent code (``chat_deepagent`` and ``subagents/*``) keeps working
until that stack is retired.
"""

from app.agents.shared.middleware import (
    ActionLogMiddleware,
    AnonymousDocumentMiddleware,
    BuiltinSkillsBackend,
    BusyMutexMiddleware,
    ClearToolUsesEdit,
    DedupHITLToolCallsMiddleware,
    DoomLoopMiddleware,
    FileIntentMiddleware,
    FlattenSystemMessageMiddleware,
    KnowledgeBasePersistenceMiddleware,
    KnowledgeBaseSearchMiddleware,
    KnowledgePriorityMiddleware,
    KnowledgeTreeMiddleware,
    MemoryInjectionMiddleware,
    NoopInjectionMiddleware,
    OtelSpanMiddleware,
    PermissionMiddleware,
    RetryAfterMiddleware,
    SearchSpaceSkillsBackend,
    SpillingContextEditingMiddleware,
    SpillToBackendEdit,
    SurfSenseCompactionMiddleware,
    SurfSenseFilesystemMiddleware,
    ToolCallNameRepairMiddleware,
    build_skills_backend_factory,
    commit_staged_filesystem_state,
    create_surfsense_compaction_middleware,
    default_skills_sources,
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
