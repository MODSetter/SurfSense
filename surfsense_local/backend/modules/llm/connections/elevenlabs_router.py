from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.dependencies import SessionDep, transact
from modules.llm.catalog.remote.rows import CUSTOM
from modules.llm.connections.elevenlabs_key import require_usable_key
from modules.llm.connections.router import save_connection
from modules.llm.connections.serves import served_by
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection
from modules.llm.providers.elevenlabs.account import API_URL, ELEVENLABS
from modules.llm.schemas import ConnectionRead

router = APIRouter(prefix="/connections")


class ElevenLabsOption(BaseModel):
    serves: list[ModelType]


class ElevenLabsWrite(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    api_key: str = Field(min_length=1, max_length=4096)


@router.get("/elevenlabs")
def elevenlabs_option() -> ElevenLabsOption:
    """Which slots offer it, so no picker decides."""
    return ElevenLabsOption(serves=list(served_by(ELEVENLABS)))


@router.post("/elevenlabs", status_code=status.HTTP_201_CREATED)
async def connect_elevenlabs(
    payload: ElevenLabsWrite, session: SessionDep
) -> ConnectionRead:
    label = payload.label.strip()
    api_key = payload.api_key.strip()
    if not label or not api_key:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "name and key must not be empty"
        )
    await require_usable_key(session, API_URL, api_key)
    connection = ProviderConnection(
        label=label,
        # What the table's check takes; `auth_kind` says which API it speaks.
        provider="openai_compatible",
        base_url=API_URL,
        catalog_provider=CUSTOM,
        auth_kind=ELEVENLABS,
    )
    connection.api_key = api_key
    session.add(connection)
    return await transact(session, save_connection, connection)
