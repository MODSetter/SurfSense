import httpx
from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.dependencies import SessionDep
from modules.llm.connections.service import (
    discover_models,
    normalize_base_url,
    probe_connection,
)
from modules.llm.models import ProviderConnection
from modules.llm.providers.openai_compatible import (
    NonRetryableImageError,
    OpenAICompatibleImageProvider,
)
from modules.llm.schemas import (
    ConnectionModelRead,
    ConnectionRead,
    ConnectionWrite,
    ImageTestWrite,
)

router = APIRouter(prefix="/connections")

DEFAULT_IMAGE_TEST_PROMPT = (
    "A simple blue circle centered on a plain white background."
)


def _read(connection: ProviderConnection) -> ConnectionRead:
    return ConnectionRead(
        id=connection.id,
        label=connection.label,
        provider=connection.provider,
        base_url=connection.base_url,
        has_api_key=connection.api_key is not None,
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


def _candidate(payload: ConnectionWrite) -> tuple[str, str, str | None]:
    label = payload.label.strip()
    if not label:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "label must not be empty"
        )
    if payload.provider != "openai_compatible":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unknown connection provider: {payload.provider}",
        )
    try:
        base_url = normalize_base_url(payload.base_url)
    except ValueError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)
        ) from error
    api_key = payload.api_key
    if api_key is not None:
        api_key = api_key.strip()
        if not api_key:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "api key must be null or non-empty",
            )
    return label, base_url, api_key


async def _probe_or_reject(
    base_url: str, api_key: str | None, allow_unverified: bool
) -> None:
    try:
        await probe_connection(base_url, api_key)
    except (httpx.HTTPError, ValueError) as error:
        if allow_unverified:
            return
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "unverified_connection",
                "message": "The endpoint's model list could not be verified.",
            },
        ) from error


@router.get("", response_model=list[ConnectionRead])
def list_connections(session: SessionDep) -> list[ConnectionRead]:
    connections = session.scalars(
        select(ProviderConnection).order_by(ProviderConnection.label)
    ).all()
    return [_read(connection) for connection in connections]


@router.post("", response_model=ConnectionRead, status_code=status.HTTP_201_CREATED)
async def create_connection(
    payload: ConnectionWrite, session: SessionDep
) -> ConnectionRead:
    label, base_url, api_key = _candidate(payload)
    await _probe_or_reject(base_url, api_key, payload.allow_unverified)
    connection = ProviderConnection(
        label=label,
        provider=payload.provider,
        base_url=base_url,
        api_key=api_key,
    )
    session.add(connection)
    try:
        session.flush()
    except IntegrityError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a connection with this label already exists"
        ) from error
    return _read(connection)


@router.put("/{connection_id}", response_model=ConnectionRead)
async def update_connection(
    connection_id: int, payload: ConnectionWrite, session: SessionDep
) -> ConnectionRead:
    connection = session.get(ProviderConnection, connection_id)
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "connection not found")
    label, base_url, submitted_key = _candidate(payload)
    api_key = (
        submitted_key
        if "api_key" in payload.model_fields_set
        else connection.api_key
    )
    await _probe_or_reject(base_url, api_key, payload.allow_unverified)
    connection.label = label
    connection.provider = payload.provider
    connection.base_url = base_url
    connection.api_key = api_key
    try:
        session.flush()
    except IntegrityError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a connection with this label already exists"
        ) from error
    return _read(connection)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(connection_id: int, session: SessionDep) -> Response:
    connection = session.get(ProviderConnection, connection_id)
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "connection not found")
    session.delete(connection)
    session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{connection_id}/models", response_model=list[ConnectionModelRead])
async def list_connection_models(
    connection_id: int, session: SessionDep
) -> list[ConnectionModelRead]:
    connection = session.get(ProviderConnection, connection_id)
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "connection not found")
    try:
        models = await discover_models(connection)
    except httpx.HTTPError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "connection model discovery failed"
        ) from error
    except ValueError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
    return [
        ConnectionModelRead(
            connection_id=connection.id,
            connection_label=connection.label,
            name=model.name,
            capabilities=list(model.capabilities),
            capability_known=model.capability_known,
        )
        for model in models
    ]


@router.post("/{connection_id}/image-test")
async def test_connection_image(
    connection_id: int, payload: ImageTestWrite, session: SessionDep
) -> Response:
    connection = session.get(ProviderConnection, connection_id)
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "connection not found")
    provider = OpenAICompatibleImageProvider(
        connection.id, connection.base_url, connection.api_key
    )
    model = payload.model.strip()
    if not model:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "model name must not be empty",
        )
    try:
        image = await provider.generate(
            model, payload.prompt or DEFAULT_IMAGE_TEST_PROMPT
        )
    except NonRetryableImageError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
    return Response(
        content=image.content,
        media_type=image.media_type,
        headers={"Cache-Control": "no-store"},
    )
