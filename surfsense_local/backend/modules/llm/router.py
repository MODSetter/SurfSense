import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from api.dependencies import SessionDep
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm.activity import ModelBusyError, model_activity
from modules.llm.credentials import (
    clear_provider_key,
    read_provider_key,
    write_provider_key,
)
from modules.llm.dependencies import ProviderDep, StoreDep
from modules.llm.models import ModelRole, OnboardingCompletion, SelectedModel
from modules.llm.providers import get_provider, provider_names
from modules.llm.providers.protocols import ModelStore
from modules.llm.recommendations.dependencies import CatalogServiceDep
from modules.llm.recommendations.router import router as recommendations_router
from modules.llm.schemas import (
    CatalogEntryRead,
    CredentialStatus,
    CredentialWrite,
    ModelDeleteRead,
    ModelRead,
    OnboardingStatusRead,
    ProviderRead,
    PullRequest,
    SelectionRead,
    SelectionWrite,
)
from modules.llm.selection import choose_model

router = APIRouter(prefix="/llm", tags=["llm"])
router.include_router(recommendations_router)


@router.get(
    "/onboarding",
    response_model=OnboardingStatusRead,
    summary="Read model onboarding status",
)
def read_onboarding_status(session: SessionDep) -> OnboardingStatusRead:
    return OnboardingStatusRead(
        completed=session.get(OnboardingCompletion, 1) is not None
    )


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


@router.delete(
    "/providers/{provider}/models/{model_name:path}",
    response_model=ModelDeleteRead,
    summary="Delete an installed local generation model",
)
async def delete_model(
    model_name: str,
    store: StoreDep,
    service: CatalogServiceDep,
    session: SessionDep,
) -> ModelDeleteRead:
    installed = next(
        (model for model in await store.models() if model.name == model_name),
        None,
    )
    if installed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"model not found: {model_name}")
    if "completion" not in installed.capabilities:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"model does not support generation: {model_name}",
        )
    # ponytail: Studio does not persist the model used by each job, so block all
    # local deletes while one runs. Record provider/model per job to narrow this.
    studio_running = session.scalar(
        select(Document.id)
        .where(
            Document.document_type == DocumentType.ARTIFACT,
            Document.status == DocumentStatus.PROCESSING,
        )
        .limit(1)
    )
    if studio_running is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "a model cannot be deleted while Studio is generating",
        )
    install_lock = service.install_lock(store.name)
    if install_lock.locked():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{store.name} is currently installing a model",
        )
    await install_lock.acquire()

    try:
        try:
            async with model_activity.deleting((store.name, model_name)):
                await store.delete(model_name)
        except ModelBusyError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    finally:
        install_lock.release()

    selected = session.get(SelectedModel, ModelRole.GENERATION)
    selection_cleared = (
        selected is not None
        and selected.provider == store.name
        and selected.name == model_name
    )
    if selection_cleared:
        session.delete(selected)
    return ModelDeleteRead(name=model_name, selection_cleared=selection_cleared)


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
async def pull_model(
    store: StoreDep,
    payload: PullRequest,
    service: CatalogServiceDep,
) -> StreamingResponse:
    lock = service.install_lock(store.name)
    if lock.locked():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{store.name} is already installing a model",
        )
    await lock.acquire()

    async def progress() -> AsyncIterator[bytes]:
        try:
            async for step in store.pull(payload.name):
                line = {
                    "status": step.status,
                    "completed": step.completed,
                    "total": step.total,
                }
                yield (json.dumps(line) + "\n").encode()
        finally:
            lock.release()

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
    return await choose_model(session, role, payload.provider, payload.name)
