"""The user's opt-in to try the agent on the selected text model."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import SessionDep
from modules.llm.capability.agent_trial import set_agent_trial
from modules.llm.capability.level import Level
from modules.llm.capability.read import capability_read, trial_block
from modules.llm.capability.resolve import capability_of
from modules.llm.capability.schemas import AgentTrialWrite, CapabilityRead
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.reads_images import connection_catalog_provider

router = APIRouter(prefix="/selection/text_gen/agent-trial", tags=["llm"])


@router.put(
    "",
    response_model=CapabilityRead,
    summary="Turn the agent trial on or off for the selected text model",
)
def set_trial(payload: AgentTrialWrite, session: SessionDep) -> CapabilityRead:
    selected = _text_model(session)
    catalog_provider = connection_catalog_provider(session, selected)
    if payload.enabled:
        _refuse_unless_offered(selected, catalog_provider)
    set_agent_trial(selected, payload.enabled)
    session.commit()
    return capability_read(selected, catalog_provider)


def _text_model(session: Session) -> SelectedModel:
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no chat model chosen")
    return selected


def _refuse_unless_offered(
    selected: SelectedModel, catalog_provider: str | None
) -> None:
    capability = capability_of(selected.name, selected.connection)
    if capability.level is not Level.NOT_MEASURED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "measured",
                "message": "This model was measured; its level decides the agent.",
            },
        )
    blocked = trial_block(selected, catalog_provider)
    if blocked is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": blocked, "message": "This model cannot run the agent."},
        )
