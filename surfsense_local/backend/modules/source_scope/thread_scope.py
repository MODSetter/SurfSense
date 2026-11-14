from collections.abc import Sequence

from sqlalchemy.orm import Session

from modules.chat.models import ChatThread
from modules.source_scope.mentioned import (
    mentioned_of,
    stored_with_mentions,
    ticks_of,
    with_mentions,
)
from modules.source_scope.resolve import ResolvedScope, pruned, resolve_scope
from modules.source_scope.schemas import ALL_SOURCES, SourceScope


def thread_ticks(thread: ChatThread) -> SourceScope:
    """The thread's stored ticks; a thread that never stored any uses every source."""
    if thread.source_scope is None:
        return ALL_SOURCES
    return SourceScope.model_validate(ticks_of(thread.source_scope))


def thread_scope(thread: ChatThread) -> SourceScope:
    """What the thread works from: its ticks and every source its messages named."""
    return with_mentions(thread_ticks(thread), mentioned_of(thread.source_scope))


def store_thread_scope(
    session: Session,
    thread: ChatThread,
    scope: SourceScope,
    mentioned: Sequence[int] = (),
) -> tuple[SourceScope, ResolvedScope]:
    """Validate ticks against the thread's workspace and keep them, pruned, with what
    its messages named; returns the scope the thread now works from."""
    named = list(dict.fromkeys([*mentioned_of(thread.source_scope), *mentioned]))
    resolved = resolve_scope(session, thread.workspace_id, with_mentions(scope, named))
    kept = pruned(scope, resolved)
    kept_named = [i for i in named if i not in resolved.removed_document_ids]
    thread.source_scope = stored_with_mentions(kept, kept_named)
    session.flush()
    return with_mentions(kept, kept_named), resolved
