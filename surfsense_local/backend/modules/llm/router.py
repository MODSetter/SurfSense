import json
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.egress import service as egress
from modules.llm.activity import ModelBusyError, model_activity, model_key
from modules.llm.catalog.dependencies import CatalogServiceDep
from modules.llm.catalog.remote.router import router as remote_catalog_router
from modules.llm.catalog.router import router as catalog_router
from modules.llm.connections.router import router as connections_router
from modules.llm.dependencies import LocalRuntimeDep, ProviderDep
from modules.llm.model_type import ModelType
from modules.llm.models import OnboardingCompletion, SelectedModel
from modules.llm.providers import get_provider, llamacpp, provider_names
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.residency import warm_selected
from modules.llm.schemas import (
    LocalImageCatalogRead,
    LocalImageModelRead,
    LocalImageRuntimeRead,
    ModelDeleteRead,
    ModelRead,
    OnboardingStatusRead,
    ProviderRead,
    SelectionRead,
    SelectionWrite,
)
from modules.llm.selection import choose_model, complete_onboarding
from shared.config import get_llm_settings

router = APIRouter(prefix="/llm", tags=["llm"])
router.include_router(catalog_router)
router.include_router(remote_catalog_router)
router.include_router(connections_router)


@router.get(
    "/onboarding",
    response_model=OnboardingStatusRead,
    summary="Read model onboarding status",
)
def read_onboarding_status(session: SessionDep) -> OnboardingStatusRead:
    return OnboardingStatusRead(
        completed=session.get(OnboardingCompletion, 1) is not None
    )


@router.post(
    "/onboarding",
    response_model=OnboardingStatusRead,
    summary="Complete model onboarding",
)
def mark_onboarding_complete(session: SessionDep) -> OnboardingStatusRead:
    complete_onboarding(session)
    return OnboardingStatusRead(completed=True)


@router.get("/providers", response_model=list[ProviderRead], summary="List providers")
async def list_providers() -> list[ProviderRead]:
    providers = [get_provider(name) for name in provider_names()]
    return [
        ProviderRead(
            name=provider.name,
            healthy=await provider.health(),
            # Downloading is a catalog capability now, not a runtime one: the
            # local runtime's models install through POST /llm/install, and a
            # remote endpoint's cannot be installed at all.
            can_download=provider.name == llamacpp.PROVIDER,
            requires_key=getattr(provider, "requires_key", False),
            configured=True,
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
    """The runtime reports files by their real names, so there is nothing to
    clean up: the previous runtime's registry tags needed tidying, these do not."""
    return [
        ModelRead(
            name=model.name,
            installed=model.installed,
            capabilities=list(model.capabilities),
            display_name=model.display_name or model.name,
        )
        for model in await provider.models()
    ]


@router.delete(
    "/models/{model_name:path}",
    response_model=ModelDeleteRead,
    summary="Delete an installed local generation model",
)
async def delete_model(
    model_name: str,
    store: LocalRuntimeDep,
    service: CatalogServiceDep,
    session: SessionDep,
) -> ModelDeleteRead:
    # Inventory from disk, not from the runtime. Asking the router first meant a
    # dead router made models undeletable, which is backwards: one reason to
    # delete a model is that things are broken, and removing a file needs
    # nothing running.
    installed = next(
        (row for row in service.installed() if row.model_id == model_name), None
    )
    if installed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"model not found: {model_name}")
    if await transact(session, _studio_running):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "a model cannot be deleted while Studio is generating",
        )
    install_lock = service.install_lock()
    if install_lock.locked():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "a model is already being installed",
        )
    await install_lock.acquire()

    try:
        try:
            async with model_activity.deleting(model_key(store.name, model_name)):
                await store.delete(model_name)
        except ModelBusyError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        except FileNotFoundError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"model not found: {model_name}"
            ) from error
        # Rewrite the preset so the router drops it on the next restart, and so
        # it never advertises a model whose file is gone: a stale section is
        # served as a real entry, `source: preset`, and fails when chosen.
        service.reprice()
    finally:
        install_lock.release()

    selection_cleared = await transact(
        session, _clear_selection, store.name, model_name
    )
    return ModelDeleteRead(name=model_name, selection_cleared=selection_cleared)


def _studio_running(session: Session) -> bool:
    # ponytail: Studio does not persist the model used by each job, so block all
    # local deletes while one runs. Record provider/model per job to narrow this.
    return (
        session.scalar(
            select(Document.id)
            .where(
                Document.document_type == DocumentType.ARTIFACT,
                Document.status == DocumentStatus.PROCESSING,
            )
            .limit(1)
        )
        is not None
    )


def _clear_selection(session: Session, provider: str, model_name: str) -> bool:
    """Drop the generation selection if it named the model just deleted."""
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    cleared = (
        selected is not None
        and selected.provider == provider
        and selected.name == model_name
    )
    if cleared:
        session.delete(selected)
    return cleared


@router.get(
    "/image/local",
    response_model=LocalImageCatalogRead,
    summary="The bundled image models and their state",
)
async def read_local_image_models(session: SessionDep) -> LocalImageCatalogRead:
    chosen = await transact(session, _chosen_image_model)
    selected = chosen.name if chosen and chosen.provider == sdcpp.PROVIDER else None
    return LocalImageCatalogRead(
        provider=sdcpp.PROVIDER,
        offered=sdcpp.offered(),
        # Electron starts sd-server once weights land, so a model reads as
        # installed a few seconds before it is ready to answer.
        ready=selected is not None and await _image_server_healthy(),
        models=[
            LocalImageModelRead(
                name=model.name,
                label=model.label,
                detail=model.detail,
                size_bytes=model.size_bytes,
                installed=sdcpp.installed(model),
                selected=model.name == selected,
            )
            for model in sdcpp.CATALOG
        ],
    )


@router.get(
    "/image/local/runtime",
    response_model=LocalImageRuntimeRead,
    summary="The image model sd-server should be running",
)
def read_local_image_runtime(session: SessionDep) -> LocalImageRuntimeRead:
    chosen = _chosen_image_model(session)
    model = (
        sdcpp.find(chosen.name)
        if chosen is not None and chosen.provider == sdcpp.PROVIDER
        else None
    )
    if model is None or not sdcpp.installed(model):
        return LocalImageRuntimeRead(file=None, args=[])
    return LocalImageRuntimeRead(file=model.file, args=list(model.args))


@router.delete(
    "/image/local/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one downloaded image model",
)
async def delete_local_image_model(name: str, session: SessionDep) -> Response:
    model = sdcpp.find(name)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown image model: {name}")
    chosen = await transact(session, _chosen_image_model)
    if chosen is not None and chosen.provider == sdcpp.PROVIDER and chosen.name == name:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{model.label} is in use; choose another image model first",
        )
    sdcpp.remove(model)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/image/local/{name}/install",
    summary="Download one bundled image model, streaming progress",
)
async def install_local_image_model(
    name: str, session: SessionDep
) -> StreamingResponse:
    if not sdcpp.offered():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "this build has no local image support",
        )
    model = sdcpp.find(name)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown image model: {name}")
    await transact(session, egress.require, egress.HUGGINGFACE)

    async def progress() -> AsyncIterator[bytes]:
        async for step in sdcpp.install(model):
            line = {
                "status": step.status,
                "completed": step.completed,
                "total": step.total,
            }
            yield (json.dumps(line) + "\n").encode()

    return StreamingResponse(progress(), media_type="application/x-ndjson")


def _chosen_image_model(session: Session) -> SelectedModel | None:
    return session.get(SelectedModel, ModelType.IMAGE_GEN)


async def _image_server_healthy() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            reply = await client.get(f"{sdcpp.base_url()}/models")
            return reply.status_code == 200
    except httpx.HTTPError:
        return False


@router.get(
    "/selection/{model_type}",
    response_model=SelectionRead,
    summary="Read the model chosen for a model type",
)
def read_selection(model_type: ModelType, session: SessionDep) -> SelectedModel:
    selected = session.get(SelectedModel, model_type)
    if selected is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"no model chosen for {model_type}"
        )

    return selected


@router.put(
    "/selection/{model_type}",
    response_model=SelectionRead,
    summary="Choose the model for a model type",
)
async def set_selection(
    model_type: ModelType,
    payload: SelectionWrite,
    session: SessionDep,
    background: BackgroundTasks,
) -> SelectedModel:
    chosen = await choose_model(
        session,
        model_type,
        payload.provider,
        payload.name,
        connection_id=payload.connection_id,
        allow_unlisted=payload.allow_unlisted,
    )
    # After the response, never during it: the load blocks until the model is
    # resident, which is the tens of seconds this exists to move somewhere the
    # user is not waiting. Choosing a model is the moment they have said they
    # are about to use it, and `--models-max 1` means the load is happening
    # either way — the only question is whether it happens now or on their
    # first question.
    background.add_task(warm_selected, chosen, get_llm_settings().llamacpp_base_url)
    return chosen
