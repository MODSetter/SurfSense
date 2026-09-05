import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from api.dependencies import SessionDep
from modules.chat.dependencies import ThreadDep
from modules.chat.history import build_messages
from modules.chat.models import ChatMessage, ChatThread, MessageRole
from modules.chat.prompt import build_context
from modules.chat.schemas import (
    MessageCreate,
    MessageRead,
    ThreadCreate,
    ThreadRead,
)
from modules.llm.models import ModelRole, SelectedModel
from modules.llm.providers import get_provider
from modules.workspaces.dependencies import WorkspaceDep
from shared.search import retrieve

router = APIRouter(tags=["chat"])


@router.post(
    "/workspaces/{workspace_id}/chat/threads",
    response_model=ThreadRead,
    status_code=status.HTTP_201_CREATED,
    summary="Open a chat thread",
)
def create_thread(
    workspace: WorkspaceDep, payload: ThreadCreate, session: SessionDep
) -> ChatThread:
    thread = ChatThread(workspace_id=workspace.id, title=payload.title)
    session.add(thread)
    session.flush()  # The id and timestamps come from the database.
    return thread


@router.get(
    "/workspaces/{workspace_id}/chat/threads",
    response_model=list[ThreadRead],
    summary="List chat threads",
)
def list_threads(
    workspace: WorkspaceDep, session: SessionDep
) -> Sequence[ChatThread]:
    return session.scalars(
        select(ChatThread)
        .where(ChatThread.workspace_id == workspace.id)
        .order_by(ChatThread.created_at.desc())
    ).all()


@router.get(
    "/chat/threads/{thread_id}/messages",
    response_model=list[MessageRead],
    summary="Read a thread's messages",
)
def list_messages(thread: ThreadDep, session: SessionDep) -> Sequence[ChatMessage]:
    return session.scalars(
        select(ChatMessage)
        .where(ChatMessage.chat_thread_id == thread.id)
        .order_by(ChatMessage.created_at)
    ).all()


@router.delete(
    "/chat/threads/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a thread and its messages",
)
def delete_thread(thread: ThreadDep, session: SessionDep) -> Response:
    session.delete(thread)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/chat/threads/{thread_id}/messages",
    summary="Send a message and stream the grounded reply",
)
async def send_message(
    thread: ThreadDep, payload: MessageCreate, session: SessionDep
) -> StreamingResponse:
    selected = session.get(SelectedModel, ModelRole.GENERATION)
    if selected is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no chat model selected")
    generator = get_provider(selected.provider, session)
    if generator is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"unknown provider: {selected.provider}"
        )
    # Keep numpy/onnxruntime lazy: only chat and ingestion need this module.
    from worker.ingestion.embedding import missing_embedding_files

    if missing_embedding_files():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "local embedding model is not installed; "
            "run `uv run scripts/fetch_embedding_model.py`",
        )

    # History is the turns already stored; the new user turn is appended after.
    history = session.scalars(
        select(ChatMessage)
        .where(ChatMessage.chat_thread_id == thread.id)
        .order_by(ChatMessage.created_at)
    ).all()
    hits = retrieve(session, thread.workspace_id, payload.text)
    context, citations = build_context(hits)
    messages = build_messages(context, history, payload.text)

    session.add(
        ChatMessage(
            chat_thread_id=thread.id,
            role=MessageRole.USER,
            content={"text": payload.text},
        )
    )

    cited = [asdict(citation) for citation in citations]

    async def stream() -> AsyncIterator[bytes]:
        parts: list[str] = []
        try:
            async for delta in generator.chat(selected.name, messages):
                parts.append(delta)
                yield _frame({"type": "delta", "text": delta})
        except Exception as exc:
            # Surfaced as an event; the partial turn is still stored below.
            yield _frame({"type": "error", "message": str(exc)})

        if cited:
            yield _frame({"type": "citations", "items": cited})

        # Written as the stream closes; the request session commits it on exit.
        session.add(
            ChatMessage(
                chat_thread_id=thread.id,
                role=MessageRole.ASSISTANT,
                content={"text": "".join(parts), "citations": cited},
            )
        )
        yield _DONE

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        # Keep a proxy from buffering or caching a live stream into one late blob.
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _frame(payload: dict) -> bytes:
    """One SSE data frame: deltas, then a citations frame, then the sentinel."""
    return f"data: {json.dumps(payload)}\n\n".encode()


_DONE = b"data: [DONE]\n\n"
