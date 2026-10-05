"""Which sources an agent turn works from, resolved as a chat resolves them."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.agent_threads.scope_note import scope_note, scope_titles
from modules.chat.models import ChatThread
from modules.chat.schemas import MessageCreate
from modules.documents.sources import load_selected_sources
from modules.source_scope.resolve import resolve_scope
from modules.source_scope.thread_scope import store_thread_scope, thread_scope


@dataclass(frozen=True)
class TurnSources:
    """The turn's ready source ids, the note naming them, and how the turn shows them.

    `document_ids` None is the whole workspace: no note, no line.
    """

    document_ids: list[int] | None
    note: str | None
    shown: dict[str, Any] | None


def turn_sources(
    session: Session, thread: ChatThread, payload: MessageCreate
) -> TurnSources:
    """A sent scope is stored and resolved; else an id list as sent; else the stored scope.

    Resolved ids are never capped: a ticked folder of any size is the whole turn.
    A thread that never stored a scope keeps the whole workspace, as before scopes.
    """
    workspace_id = thread.workspace_id
    # Ticked but not ready yet; an id list names only ready sources.
    indexing = 0
    if payload.source_scope is not None:
        _, resolved = store_thread_scope(session, thread, payload.source_scope)
        ids: list[int] | None = resolved.ids
        indexing = resolved.counts.indexing
    elif payload.document_ids is not None:
        ids = [
            document.id
            for document in load_selected_sources(
                session, workspace_id, payload.document_ids
            )
        ]
    elif thread.source_scope is not None:
        resolved = resolve_scope(session, workspace_id, thread_scope(thread))
        ids = resolved.ids
        indexing = resolved.counts.indexing
    else:
        ids = None
    if ids is None:
        return TurnSources(None, None, None)
    titles = scope_titles(session, workspace_id, ids)
    return TurnSources(
        ids,
        scope_note(session, workspace_id, ids, indexing),
        {"document_ids": ids, "titles": [titles[i] for i in ids]},
    )
