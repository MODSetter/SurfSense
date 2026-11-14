"""The composer's mode switch: a pick is the model's default for new chats from then on."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from modules.llm.capability.agent_gate import catalog_facts
from modules.llm.capability.modes.mode import ChatMode
from modules.llm.capability.modes.new_chat import new_chat_modes
from modules.llm.capability.modes.remembered import remember_mode
from modules.llm.capability.read import modes_read
from modules.llm.capability.schemas import ModesRead
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.reads_images import connection_catalog_provider

__all__ = ["router"]

router = APIRouter()


class ModePick(BaseModel):
    mode: ChatMode
    # The model it was picked on: the slot may hold another by the time this arrives.
    provider: str
    connection_id: int | None
    name: str


@router.put(
    "/selection/text_gen/mode",
    response_model=ModesRead,
    summary="Pick the mode new chats on the chosen chat model start in",
)
async def pick_mode(payload: ModePick, session: SessionDep) -> ModesRead:
    return await transact(session, _pick, payload)


def _pick(session: Session, pick: ModePick) -> ModesRead:
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no chat model chosen")
    if (selected.provider, selected.connection_id, selected.name) != (
        pick.provider,
        pick.connection_id,
        pick.name,
    ):
        # Never saved: under the selected model it would be a mode nobody chose for it.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "model_changed",
                "message": "The chat model changed before this pick was saved.",
            },
        )
    facts = catalog_facts(selected, connection_catalog_provider(session, selected))
    blocked = new_chat_modes(selected, facts).blocked
    if pick.mode is ChatMode.AGENTIC and blocked is not None:
        # Never saved: the model's default stays a mode it can run.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": blocked, "message": "This model can't run Agentic."},
        )
    remember_mode(selected, pick.mode)
    return modes_read(new_chat_modes(selected, facts))
