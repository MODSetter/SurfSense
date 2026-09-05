import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from api.dependencies import SessionDep
from modules.llm.credentials import (
    clear_provider_key,
    read_provider_key,
    write_provider_key,
)
from modules.llm.dependencies import ProviderDep, StoreDep
from modules.llm.models import ModelRole, SelectedModel
from modules.llm.providers import get_provider, provider_names
from modules.llm.providers.protocols import ModelStore
from modules.llm.schemas import (
    CatalogEntryRead,
    CredentialStatus,
    CredentialWrite,
    ModelRead,
    ProviderRead,
    PullRequest,
    SelectionRead,
    SelectionWrite,
)

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/providers", response_model=list[ProviderRead], summary="List providers")
async def list_providers(session: SessionDep) -> list[ProviderRead]:
    providers = [get_provider(name, session) for name in provider_names()]
    return [
        ProviderRead(
            name=provider.name,
            healthy=await provider.health(),
            can_download=isinstance(provider, ModelStore),
            requires_key=getattr(provider, "requires_key", False),
            configured=not getattr(provider, "requires_key", False)
            or read_provider_key(session, provider.name) is not None,
        )
        for provider in providers
        if provider is not None
    ]


@router.get(
    "/providers/{provider}/models",
    response_model=list[ModelRead],
    summary="List installed models",
)
async def list_models(provider: ProviderDep) -> list[ModelRead]:
    return [
        ModelRead(
            name=model.name,
            installed=model.installed,
            capabilities=list(model.capabilities),
        )
        for model in await provider.models()
    ]


@router.get(
    "/providers/{provider}/catalog",
    response_model=list[CatalogEntryRead],
    summary="List models on offer to download",
)
async def list_catalog(provider: ProviderDep) -> list[CatalogEntryRead]:
    if not isinstance(provider, ModelStore):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{provider.name} has no catalog to download"
        )

    installed = {model.name for model in await provider.models()}
    return [
        CatalogEntryRead(
            name=entry.name,
            label=entry.label,
            size_gb=entry.size_gb,
            installed=entry.name in installed,
        )
        for entry in provider.catalog()
    ]


@router.post(
    "/providers/{provider}/pull",
    summary="Download a model, streaming progress",
)
async def pull_model(store: StoreDep, payload: PullRequest) -> StreamingResponse:
    async def progress() -> AsyncIterator[bytes]:
        async for step in store.pull(payload.name):
            line = {
                "status": step.status,
                "completed": step.completed,
                "total": step.total,
            }
            yield (json.dumps(line) + "\n").encode()

    return StreamingResponse(progress(), media_type="application/x-ndjson")


@router.put(
    "/providers/{provider}/credentials",
    response_model=CredentialStatus,
    summary="Set a provider's API key",
)
def set_credential(
    provider: str, payload: CredentialWrite, session: SessionDep
) -> CredentialStatus:
    found = get_provider(provider)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown provider: {provider}")
    if not getattr(found, "requires_key", False):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{provider} needs no API key")

    key = payload.api_key.strip()
    if not key:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "api key must not be empty"
        )

    write_provider_key(session, provider, key)
    return CredentialStatus(provider=provider, configured=True)


@router.delete(
    "/providers/{provider}/credentials",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a provider's API key",
)
def clear_credential(provider: str, session: SessionDep) -> Response:
    if get_provider(provider) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown provider: {provider}")
    clear_provider_key(session, provider)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/selection/{role}",
    response_model=SelectionRead,
    summary="Read the model chosen for a role",
)
def read_selection(role: ModelRole, session: SessionDep) -> SelectedModel:
    selected = session.get(SelectedModel, role)
    if selected is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no model chosen for {role}")

    return selected


@router.put(
    "/selection/{role}",
    response_model=SelectionRead,
    summary="Choose the model for a role",
)
async def set_selection(
    role: ModelRole, payload: SelectionWrite, session: SessionDep
) -> SelectedModel:
    provider = get_provider(payload.provider, session)
    if provider is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unknown provider: {payload.provider}",
        )

    model = next(
        (model for model in await provider.models() if model.name == payload.name),
        None,
    )
    if model is None or not model.installed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"model is not installed: {payload.name}",
        )
    if role is ModelRole.GENERATION and "completion" not in model.capabilities:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"model does not support generation: {payload.name}",
        )

    selected = session.get(SelectedModel, role)
    if selected is None:
        selected = SelectedModel(
            role=role, provider=payload.provider, name=payload.name
        )
        session.add(selected)
    else:
        selected.provider = payload.provider
        selected.name = payload.name

    session.flush()
    return selected
