from fastapi import APIRouter

from api.dependencies import SessionDep
from modules.chat.dependencies import ThreadDep
from modules.source_scope.resolve import pruned, resolve_scope
from modules.source_scope.schemas import ScopeRead, SourceScope
from modules.source_scope.thread_scope import store_thread_scope, thread_scope
from modules.workspaces.dependencies import WorkspaceDep

router = APIRouter(tags=["source scope"])


@router.get(
    "/chat/threads/{thread_id}/source-scope",
    response_model=ScopeRead,
    summary="Read a thread's source scope and what it holds now",
)
def read_thread_scope(thread: ThreadDep, session: SessionDep) -> ScopeRead:
    scope = thread_scope(thread)
    resolved = resolve_scope(session, thread.workspace_id, scope)
    return ScopeRead(source_scope=pruned(scope, resolved), counts=resolved.counts)


@router.put(
    "/chat/threads/{thread_id}/source-scope",
    response_model=ScopeRead,
    summary="Store the sources ticked for a thread between turns",
)
def put_thread_scope(
    thread: ThreadDep, payload: SourceScope, session: SessionDep
) -> ScopeRead:
    kept, resolved = store_thread_scope(session, thread, payload)
    return ScopeRead(source_scope=kept, counts=resolved.counts)


@router.post(
    "/workspaces/{workspace_id}/source-scope/resolve",
    response_model=ScopeRead,
    summary="Count what a scope holds, for a new chat or a Studio job",
)
def resolve_draft_scope(
    workspace: WorkspaceDep, payload: SourceScope, session: SessionDep
) -> ScopeRead:
    resolved = resolve_scope(session, workspace.id, payload)
    return ScopeRead(source_scope=pruned(payload, resolved), counts=resolved.counts)
