from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from modules.chat.runs.dependencies import ChatRunsDep
from modules.chat.runs.registry import STOP_SETTLE_SECONDS
from modules.chat.runs.stream import event_stream

router = APIRouter(tags=["chat"])


@router.get(
    "/chat/threads/{thread_id}/run",
    summary="Follow the reply a thread is generating",
)
def follow_run(
    thread_id: int,
    runs: ChatRunsDep,
    after: Annotated[int, Query(ge=0)] = 0,
    last_event_id: Annotated[int | None, Header()] = None,
) -> StreamingResponse:
    """Replay the frames after `after` (or `Last-Event-ID`), then stream live.

    `404` once the run has ended: its reply is stored by then, so the caller
    reads the thread's turns instead.
    """
    run = runs.get(thread_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "this thread is not answering")
    return event_stream(
        run.follow(last_event_id if last_event_id is not None else after)
    )


@router.post(
    "/chat/threads/{thread_id}/run/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Stop the reply a thread is generating",
)
async def stop_run(thread_id: int, runs: ChatRunsDep) -> Response:
    """Stop the run, queued or generating; `204` also when nothing runs."""
    await runs.stop(thread_id, STOP_SETTLE_SECONDS)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# How long a quit waits for every reply to store what it has. The 5-second
# saves cover what a slower one would lose.
QUIT_SETTLE_SECONDS = 3.0


@router.get("/chat/runs", summary="Count the replies being generated")
def count_runs(runs: ChatRunsDep) -> dict[str, int]:
    """What Electron asks before quitting, to say how many would be cut off."""
    return {"active": len(runs.running())}


@router.post(
    "/chat/runs/stop-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Store and end every reply before the app quits",
)
async def stop_all_runs(runs: ChatRunsDep) -> Response:
    """Each reply keeps its text and its question, marked interrupted."""
    await runs.interrupt_all(QUIT_SETTLE_SECONDS)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
