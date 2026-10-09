from sqlalchemy.orm import Session

from modules.chat.models import ChatThread
from modules.source_scope.resolve import ResolvedScope, pruned, resolve_scope
from modules.source_scope.schemas import ALL_SOURCES, SourceScope


def thread_scope(thread: ChatThread) -> SourceScope:
    """The thread's stored ticks; a thread that never stored any uses every source."""
    if thread.source_scope is None:
        return ALL_SOURCES
    return SourceScope.model_validate(thread.source_scope)


def store_thread_scope(
    session: Session, thread: ChatThread, scope: SourceScope
) -> tuple[SourceScope, ResolvedScope]:
    """Validate a scope against the thread's workspace and keep it, pruned."""
    resolved = resolve_scope(session, thread.workspace_id, scope)
    kept = pruned(scope, resolved)
    thread.source_scope = kept.model_dump()
    session.flush()
    return kept, resolved
