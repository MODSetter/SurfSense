from typing import Annotated

from fastapi import Depends, HTTPException, status

from api.dependencies import SessionDep
from modules.chat.models import ChatThread


def get_thread(thread_id: int, session: SessionDep) -> ChatThread:
    """Resolve the thread in the path, or fail before the handler."""
    thread = session.get(ChatThread, thread_id)
    if thread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "thread not found")

    return thread


ThreadDep = Annotated[ChatThread, Depends(get_thread)]
