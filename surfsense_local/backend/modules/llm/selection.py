import logging

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.connections import discover_models
from modules.llm.connections.router import allowed_connection
from modules.llm.model_type import ModelType
from modules.llm.models import OnboardingCompletion, SelectedModel
from modules.llm.profile import Fingerprint, from_name
from modules.llm.providers import audiocpp, get_provider, llamacpp
from modules.llm.providers.openai_compatible import OpenAICompatibleChatProvider
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.selectable import selectable_for

logger = logging.getLogger(__name__)


async def choose_model(
    session: Session,
    model_type: ModelType,
    provider_name: str,
    model_name: str,
    *,
    connection_id: int | None = None,
    allow_unlisted: bool = False,
) -> SelectedModel:
    model_name = model_name.strip()
    if not model_name:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "model name must not be empty",
        )

    if provider_name == llamacpp.PROVIDER:
        await _validate_local(model_type, model_name, connection_id)
    elif provider_name == sdcpp.PROVIDER:
        _validate_local_image(model_type, model_name, connection_id)
    elif provider_name == audiocpp.PROVIDER:
        _validate_local_audio(model_type, model_name, connection_id)
    elif provider_name == "openai_compatible":
        await _validate_remote(
            session, model_type, model_name, connection_id, allow_unlisted
        )
    else:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unknown provider: {provider_name}",
        )

    fingerprint = await _collect(session, provider_name, model_name, connection_id)
    selected = await transact(
        session,
        _store,
        model_type,
        provider_name,
        connection_id,
        model_name,
        fingerprint,
    )
    logger.info(
        "llm: %s model %s/%s gets the %s prompt (params_b=%s vendor=%s line=%s)",
        model_type.value,
        provider_name,
        model_name,
        selected.tier,
        fingerprint.params_b,
        fingerprint.vendor,
        fingerprint.line,
    )
    return selected


async def _collect(
    session: Session,
    provider_name: str,
    model_name: str,
    connection_id: int | None,
) -> Fingerprint:
    """Ask the provider what it knows, once, so generation never has to."""
    try:
        if provider_name == llamacpp.PROVIDER:
            provider = get_provider(llamacpp.PROVIDER)
            return await provider.inspect(model_name)
        if provider_name == "openai_compatible":
            connection = await transact(session, allowed_connection, connection_id)
            remote = OpenAICompatibleChatProvider(
                connection.base_url, connection.api_key
            )
            return await remote.inspect(model_name)
    except (httpx.HTTPError, ValueError, AttributeError):
        pass
    # An endpoint that will not describe its models, or one that writes no prose
    # to prompt at all, leaves only the name.
    return from_name(provider_name, model_name)


def _store(
    session: Session,
    model_type: ModelType,
    provider_name: str,
    connection_id: int | None,
    model_name: str,
    fingerprint: Fingerprint,
) -> SelectedModel:
    selected = session.get(SelectedModel, model_type)
    if selected is None:
        selected = SelectedModel(model_type=model_type, name=model_name)
        session.add(selected)
    selected.provider = provider_name
    selected.connection_id = connection_id
    selected.name = model_name
    selected.params_b = fingerprint.params_b
    selected.vendor = fingerprint.vendor
    selected.line = fingerprint.line
    session.flush()
    # updated_at is set by the database; load it here rather than lazily on the loop.
    session.refresh(selected)
    return selected


def complete_onboarding(session: Session) -> bool:
    if session.get(SelectedModel, ModelType.TEXT_GEN) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "chat model required",
        )
    if session.get(OnboardingCompletion, 1) is None:
        session.add(OnboardingCompletion())
        session.flush()
    return True


def _validate_local_image(
    model_type: ModelType, model_name: str, connection_id: int | None
) -> None:
    """The bundled sd-server fills the image_gen slot, and only once downloaded."""
    if model_type is not ModelType.IMAGE_GEN:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"the local image runtime does not serve {model_type}",
        )
    if connection_id is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "local selections must not include a connection",
        )
    if get_local_catalog().sdcpp.installed_image(model_name) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"image model is not installed: {model_name}",
        )


def _validate_local_audio(
    model_type: ModelType, model_name: str, connection_id: int | None
) -> None:
    """The bundled audio.cpp server fills the audio_gen slot, and only once
    downloaded: Electron starts it on what `server.json` names."""
    if model_type is not ModelType.AUDIO_GEN:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"the local audio runtime does not serve {model_type}",
        )
    if connection_id is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "local selections must not include a connection",
        )
    if not get_local_catalog().audiocpp.holds(model_name):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"audio model is not installed: {model_name}",
        )


async def _validate_local(
    model_type: ModelType, model_name: str, connection_id: int | None
) -> None:
    if model_type is not ModelType.TEXT_GEN:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"the local text runtime does not serve {model_type}",
        )
    if connection_id is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "a local selection must not name a connection",
        )
    provider = get_provider(llamacpp.PROVIDER)
    if provider is None:  # pragma: no cover - fixed registry invariant
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "the local runtime is unavailable"
        )
    model = next(
        (entry for entry in await provider.models() if entry.name == model_name),
        None,
    )
    if model is None or not model.installed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"model is not installed: {model_name}",
        )
    if model_type not in selectable_for(model.types, model.known):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"model does not support {model_type.value}: {model_name}",
        )


async def _validate_remote(
    session: Session,
    model_type: ModelType,
    model_name: str,
    connection_id: int | None,
    allow_unlisted: bool,
) -> None:
    if connection_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "remote selections require a connection",
        )
    connection = await transact(session, allowed_connection, connection_id)
    try:
        models = await discover_models(connection)
    except (httpx.HTTPError, ValueError) as error:
        if not allow_unlisted:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "connection models could not be verified; confirm manual selection",
            ) from error
        return

    model = next((entry for entry in models if entry.name == model_name), None)
    if model is None:
        if allow_unlisted:
            return
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"model is not listed by this connection: {model_name}",
        )
    if model_type not in selectable_for(model.types, model.capability_known):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"model does not support {model_type.value}: {model_name}",
        )
