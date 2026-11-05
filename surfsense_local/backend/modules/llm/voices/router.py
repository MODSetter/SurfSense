from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from modules.llm.connections.router import allowed_connection
from modules.llm.connections.speech_client import speech_client
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.providers.openai_compatible.speech import NonRetryableSpeechError
from modules.llm.providers.protocols import SpokenTurn
from modules.llm.schemas import VoiceRead
from modules.llm.voices.roster import server_roster, voices_page
from modules.llm.voices.saved import forget, keep

router = APIRouter(prefix="/selection/audio_gen/voices", tags=["llm"])

# Heard before it is kept: a voice the server refuses never reaches a podcast.
TRIAL_LINE = "Hello. This is how your podcasts will sound."

VoiceId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class VoicesProblemRead(BaseModel):
    # The interface words `no_usable_voices` itself; `list_failed` carries the server's.
    code: str
    message: str


class VoicesRead(BaseModel):
    # What a voice is played through: the connection's speech test.
    connection_id: int
    model: str
    source: str
    voices: list[VoiceRead]
    # Those removing can take away; the rest are the server's.
    added: list[str]
    voices_page: str | None
    problem: VoicesProblemRead | None = None


class VoiceWrite(BaseModel):
    voice: VoiceId
    # The line to hear it say, in the interface's language; English otherwise.
    text: str | None = Field(default=None, min_length=1, max_length=300)


@router.get("", response_model=VoicesRead)
def list_voices(session: SessionDep) -> VoicesRead:
    selected, connection = _server_selection(session)
    roster = server_roster(session, selected, connection)
    session.commit()  # egress stamps the host's last call
    return VoicesRead(
        connection_id=connection.id,
        model=selected.name,
        source=roster.source,
        voices=[VoiceRead(id=voice.id, label=voice.label) for voice in roster.voices],
        added=roster.added,
        # A list here leaves no reason to go and read the provider's page.
        voices_page=voices_page(connection, selected.name)
        if roster.source == "saved"
        else None,
        problem=VoicesProblemRead(
            code=roster.problem.code, message=roster.problem.message
        )
        if roster.problem
        else None,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_voice(payload: VoiceWrite, session: SessionDep) -> Response:
    """Voice one line in it, then keep it; a refusal keeps nothing."""
    selected, connection = await transact(session, _server_selection)
    tested = (selected.connection_id, selected.name)
    speech = speech_client(connection, selected.name)
    try:
        await speech.synthesize(
            [SpokenTurn(payload.voice, payload.text or TRIAL_LINE)], ""
        )
    except NonRetryableSpeechError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
    await transact(session, _keep, payload.voice, tested)
    return Response(status_code=status.HTTP_201_CREATED)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def remove_voice(voice: VoiceId, session: SessionDep) -> Response:
    selected, _ = _server_selection(session)
    forget(session, selected, voice)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _server_selection(session: Session) -> tuple[SelectedModel, ProviderConnection]:
    """The audio slot's server model and its connection, once egress allows it."""
    selected = session.get(SelectedModel, ModelType.AUDIO_GEN)
    if selected is None or selected.connection_id is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "the audio model is not a server's"
        )
    return selected, allowed_connection(session, selected.connection_id)


def _keep(session: Session, voice: str, tested: tuple[int | None, str]) -> None:
    """Read again, past what this session holds: voicing takes seconds, and the voice
    was only heard on the model it began on."""
    session.expire_all()
    selected, _ = _server_selection(session)
    if (selected.connection_id, selected.name) != tested:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "the audio model changed while this was tested"
        )
    keep(session, selected, voice)
