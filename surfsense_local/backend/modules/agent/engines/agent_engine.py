"""What the routes ask of whichever engine runs an agent thread's turns."""

from pathlib import Path
from typing import Any, Literal, Protocol

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from modules.agent.agent_threads.turn import RunPlace
from modules.chat.models import ChatThread
from modules.chat.schemas import MessageCreate


class AgentEngine(Protocol):
    """An engine refuses a request the way its route answers, with an HTTPException."""

    async def open_session(
        self, session: Session, thread: ChatThread, launch_key: str
    ) -> bool:
        """Give a new thread to this engine; False when it cannot answer now, and the thread stays the chat's."""
        ...

    async def run_turn(
        self,
        session: Session,
        thread: ChatThread,
        payload: MessageCreate,
        launch_key: str,
        place: RunPlace,
    ) -> StreamingResponse: ...

    async def thread_messages(
        self, session: Session, thread: ChatThread, launch_key: str, answering: bool
    ) -> list[dict[str, Any]]: ...

    async def answer_permission(
        self, thread: ChatThread, request_id: str, reply: Literal["once", "reject"]
    ) -> None: ...

    async def stored_step(self, thread: ChatThread, part_id: str) -> dict[str, Any]:
        """A tool step whole, as the engine stored it: a turn's frames carry only its start."""
        ...

    async def forget_thread(self, thread: ChatThread) -> Path:
        """Stop and delete the thread's session; returns its folder, removed once the row is gone."""
        ...

    def forget_workspace(self, session: Session, workspace_id: int) -> None:
        """Every session of a workspace about to be deleted. Runs in a worker thread."""
        ...
