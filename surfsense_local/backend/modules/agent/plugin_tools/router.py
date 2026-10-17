from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from api.dependencies import SessionDep, transact
from api.notify import notify_document_updates
from modules.agent.engines.both_sessions import stored_step_of
from modules.agent.engines.thread_engine import every_engine
from modules.agent.plugin_tools.saved_results import save_result
from modules.chat.dependencies import ThreadDep
from modules.documents.tasks import ingest_document
from modules.embedding.dependencies import EMBEDDER_CHOSEN
from modules.events.dependencies import EventBrokerDep

router = APIRouter(tags=["agent"])


class SavedStep(BaseModel):
    document_id: int


@router.post(
    "/chat/threads/{thread_id}/plugin-steps/{part_id}/save",
    response_model=SavedStep,
    dependencies=[EMBEDDER_CHOSEN],
    status_code=status.HTTP_201_CREATED,
    summary="Save a plugin step's result to Sources",
)
async def save_plugin_step(
    thread: ThreadDep,
    part_id: str,
    session: SessionDep,
    broker: EventBrokerDep,
    response: Response,
) -> SavedStep:
    """201 for a new note; 200 when the same call's note was updated."""
    part = await stored_step_of(session, thread, part_id, every_engine())
    note, created = await transact(session, save_result, thread, part)
    ingest_document(note.id)
    notify_document_updates(broker, note)
    if not created:
        response.status_code = status.HTTP_200_OK
    return SavedStep(document_id=note.id)
