import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.llm.connections import discover_models
from modules.llm.models import (
    ModelRole,
    OnboardingCompletion,
    ProviderConnection,
    SelectedModel,
)
from modules.llm.providers import get_provider


async def choose_model(
    session: Session,
    role: ModelRole,
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

    if provider_name == "ollama":
        await _validate_local(role, model_name, connection_id)
    elif provider_name == "openai_compatible":
        await _validate_remote(
            session, role, model_name, connection_id, allow_unlisted
        )
    else:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unknown provider: {provider_name}",
        )

    selected = session.get(SelectedModel, role)
    if selected is None:
        selected = SelectedModel(
            role=role,
            provider=provider_name,
            connection_id=connection_id,
            name=model_name,
        )
        session.add(selected)
    else:
        selected.provider = provider_name
        selected.connection_id = connection_id
        selected.name = model_name
    session.flush()
    return selected

1   
def complete_onboarding(session: Session) -> bool:
    if session.get(SelectedModel, ModelRole.GENERATION) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "chat model required",
        )
    if session.get(OnboardingCompletion, 1) is None:
        session.add(OnboardingCompletion())
        session.flush()
    return True


async def _validate_local(
    role: ModelRole, model_name: str, connection_id: int | None
) -> None:
    if role is not ModelRole.GENERATION:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Ollama does not provide image generation",
        )
    if connection_id is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Ollama selections must not include a connection",
        )
    provider = get_provider("ollama")
    if provider is None:  # pragma: no cover - fixed registry invariant
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Ollama unavailable")
    model = next(
        (entry for entry in await provider.models() if entry.name == model_name),
        None,
    )
    if model is None or not model.installed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"model is not installed: {model_name}",
        )
    if "completion" not in model.capabilities:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"model does not support generation: {model_name}",
        )


async def _validate_remote(
    session: Session,
    role: ModelRole,
    model_name: str,
    connection_id: int | None,
    allow_unlisted: bool,
) -> None:
    if connection_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "remote selections require a connection",
        )
    connection = session.get(ProviderConnection, connection_id)
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "connection not found")
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
    required = (
        "completion"
        if role is ModelRole.GENERATION
        else "image_generation"
    )
    if model.capability_known and required not in model.capabilities:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"model does not support {role.value}: {model_name}",
        )
