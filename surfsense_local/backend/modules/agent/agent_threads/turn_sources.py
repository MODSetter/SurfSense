"""Which sources an agent turn works from: the thread's scope, stored and resolved once."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.agent_threads.scope_note import scope_note, shown_scope
from modules.chat.models import ChatThread
from modules.chat.schemas import MessageCreate
from modules.documents.sources import load_selected_sources
from modules.source_scope.resolve import ResolvedScope, resolve_scope
from modules.source_scope.schemas import SourceScope
from modules.source_scope.thread_scope import store_thread_scope, thread_scope


@dataclass(frozen=True)
class TurnSources:
    """The turn's ready source ids, which its folder mirrors, the note naming them, and how it shows them.

    A thread on every source sends no note and shows no line.
    """

    document_ids: list[int]
    note: str | None
    shown: dict[str, Any] | None


def turn_sources(
    session: Session, thread: ChatThread, payload: MessageCreate
) -> TurnSources:
    """A sent scope, or a sent id list, is stored; else the stored scope holds.

    The tools read the stored scope on each call, so what is sent must be stored.
    Resolved ids are never capped: a ticked folder of any size is the whole turn.
    """
    if payload.source_scope is not None:
        scope, resolved = store_thread_scope(session, thread, payload.source_scope)
    elif payload.document_ids is not None:
        # Checked as a chat checks them: each must exist here and be ready.
        ids = [
            document.id
            for document in load_selected_sources(
                session, thread.workspace_id, payload.document_ids
            )
        ]
        scope, resolved = store_thread_scope(
            session, thread, SourceScope(document_ids=ids)
        )
    else:
        scope = thread_scope(thread)
        resolved = resolve_scope(session, thread.workspace_id, scope)
    if _every_source(scope):
        return TurnSources(resolved.ids, None, None)
    return _noted(session, thread.workspace_id, resolved)


def _noted(session: Session, workspace_id: int, resolved: ResolvedScope) -> TurnSources:
    return TurnSources(
        resolved.ids,
        scope_note(resolved.ids, resolved.counts.indexing),
        shown_scope(session, workspace_id, resolved.ids),
    )


def _every_source(scope: SourceScope) -> bool:
    return (
        scope.all and not scope.excluded_folder_ids and not scope.excluded_document_ids
    )
