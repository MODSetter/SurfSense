from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from modules.artifacts.local_image_demand import local_image_demand
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.embedding.active import active_index
from modules.llm.activity import (
    ModelBusyError,
    ModelFileHeldError,
    model_activity,
    model_key,
)
from modules.llm.capability import capability_of
from modules.llm.capability.read import capability_read
from modules.llm.catalog.local.dependencies import LocalCatalogDep
from modules.llm.catalog.local.engines.engine import LocalEngine
from modules.llm.catalog.local.install_jobs.router import router as install_jobs_router
from modules.llm.catalog.local.router import router as local_catalog_router
from modules.llm.catalog.remote.router import router as remote_catalog_router
from modules.llm.connections.router import router as connections_router
from modules.llm.dependencies import ProviderDep
from modules.llm.local_image_state import local_image_state
from modules.llm.model_type import ModelType
from modules.llm.models import OnboardingCompletion, SelectedModel
from modules.llm.providers import get_provider, llamacpp, provider_names
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.reads_images import (
    connection_catalog_provider,
    selection_reads_images,
)
from modules.llm.residency import warm_selected
from modules.llm.schemas import (
    LocalImageRuntimeRead,
    LocalImageStateRead,
    ModelDeleteRead,
    ModelRead,
    OnboardingComplete,
    OnboardingStatusRead,
    ProviderRead,
    RuntimeFileRead,
    SelectionRead,
    SelectionWrite,
)
from modules.llm.selectable import SLOTS, selectable_for
from modules.llm.selection import choose_model, complete_onboarding
from modules.llm.subscriptions.chatgpt.router import router as chatgpt_router
from modules.llm.voices.router import router as voices_router
from shared.config import get_llm_settings

router = APIRouter(prefix="/llm", tags=["llm"])
router.include_router(local_catalog_router)
router.include_router(install_jobs_router)
router.include_router(remote_catalog_router)
# Before the connections router, so `chatgpt` is never read as a connection id.
router.include_router(chatgpt_router)
router.include_router(connections_router)
router.include_router(voices_router)


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
def mark_onboarding_complete(
    session: SessionDep, payload: Annotated[OnboardingComplete | None, Body()] = None
) -> OnboardingStatusRead:
    complete_onboarding(session, payload.embedding_model if payload else None)
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
            types=list(model.types),
            selectable_for=slots,
            capability_level=capability_of(model.name, None).level
            if provider.name == llamacpp.PROVIDER and ModelType.TEXT_GEN in slots
            else None,
        )
        for model in await provider.models()
        for slots in [selectable_for(model.types, model.known)]
    ]


@router.delete(
    "/models/{model_name:path}",
    response_model=ModelDeleteRead,
    summary="Delete an installed local generation model",
)
async def delete_model(
    model_name: str,
    service: LocalCatalogDep,
    session: SessionDep,
) -> ModelDeleteRead:
    # Inventory from disk, not from the runtime. Asking the router first meant a
    # dead router made models undeletable, which is backwards: one reason to
    # delete a model is that things are broken, and removing a file needs
    # nothing running.
    engine = service.engine_to_delete_from(model_name)
    if engine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"model not found: {model_name}")
    if engine.bundled(model_name):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{model_name} comes with SurfSense and cannot be deleted",
        )
    if await transact(session, _embeds_the_library, model_name):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{model_name} made every vector in the library and cannot be deleted",
        )
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
            async with model_activity.deleting(model_key(engine.provider, model_name)):
                # Every part of a split build and its projector, from the
                # install record, and whatever the engine settles after.
                service.remove(model_name, engine=engine.name)
        except ModelFileHeldError as error:
            # Only sd-server is stopped by an empty slot. The others keep their
            # selection until the delete works, and are told to let go.
            if engine.server_follows_selection:
                await _clear_selections(session, engine, model_name)
            await engine.release(model_name)
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{model_name} is still in use, so it is being stopped. "
                "Delete it again in a few seconds.",
            ) from error
        except ModelBusyError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        except FileNotFoundError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"model not found: {model_name}"
            ) from error
    finally:
        install_lock.release()

    selection_cleared = await _clear_selections(session, engine, model_name)
    return ModelDeleteRead(name=model_name, selection_cleared=selection_cleared)


async def _clear_selections(
    session: SessionDep, engine: LocalEngine, model_name: str
) -> bool:
    """Empty every slot of the engine's that named the model."""
    selection_cleared = False
    for model_type in engine.model_types:
        cleared = await transact(
            session, _clear_selection, engine.provider, model_name, model_type
        )
        selection_cleared = selection_cleared or cleared
    return selection_cleared


def _embeds_the_library(session: Session, model_name: str) -> bool:
    active = active_index(session)
    return active is not None and active.spec.id == model_name


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


def _clear_selection(
    session: Session,
    provider: str,
    model_name: str,
    model_type: ModelType = ModelType.TEXT_GEN,
) -> bool:
    """Drop the selection if it named the model just deleted."""
    selected = session.get(SelectedModel, model_type)
    cleared = (
        selected is not None
        and selected.provider == provider
        and selected.name == model_name
    )
    if cleared:
        session.delete(selected)
    return cleared


@router.get(
    "/image/local/runtime",
    response_model=LocalImageRuntimeRead,
    summary="The image model sd-server should be running",
)
def read_local_image_runtime(
    session: SessionDep, service: LocalCatalogDep
) -> LocalImageRuntimeRead:
    wanted = local_image_demand(session, datetime.now(UTC))
    chosen = session.get(SelectedModel, wanted) if wanted is not None else None
    image = (
        service.sdcpp.installed_image(chosen.name)
        if chosen is not None and chosen.provider == sdcpp.PROVIDER
        else None
    )
    if image is None:
        return LocalImageRuntimeRead(files=[], args=[])
    return LocalImageRuntimeRead(
        files=[RuntimeFileRead(flag=flag, path=path) for flag, path in image.files],
        args=list(image.args),
    )


def _slot(model_type: ModelType) -> ModelType:
    """The embedder is fixed with the index at onboarding, never selected."""
    if model_type not in SLOTS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "the embedding model is chosen during onboarding, not selected",
        )
    return model_type


SlotDep = Annotated[ModelType, Depends(_slot)]


@router.get(
    "/image/local/state",
    response_model=LocalImageStateRead,
    summary="Whether the chosen local image model is running, without starting it",
)
async def read_local_image_state(
    session: SessionDep,
    service: LocalCatalogDep,
    model_type: ModelType = ModelType.IMAGE_GEN,
) -> LocalImageStateRead:
    return LocalImageStateRead(
        state=await local_image_state(session, service, model_type)
    )


@router.get(
    "/selection/{model_type}",
    response_model=SelectionRead,
    summary="Read the model chosen for a model type",
)
async def read_selection(model_type: SlotDep, session: SessionDep) -> SelectionRead:
    return await _selection_read(
        session, await transact(session, _chosen_or_404, model_type)
    )


def _chosen_or_404(session: Session, model_type: ModelType) -> SelectedModel:
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
    model_type: SlotDep,
    payload: SelectionWrite,
    session: SessionDep,
    background: BackgroundTasks,
) -> SelectionRead:
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
    return await _selection_read(session, chosen)


async def _selection_read(session: Session, selected: SelectedModel) -> SelectionRead:
    read, catalog_provider = await transact(session, _read_with_provider, selected)
    read.reads_images = await selection_reads_images(selected, catalog_provider)
    return read


def _read_with_provider(
    session: Session, selected: SelectedModel
) -> tuple[SelectionRead, str | None]:
    read = SelectionRead.model_validate(selected)
    catalog_provider = connection_catalog_provider(session, selected)
    if selected.model_type is ModelType.TEXT_GEN:
        read.capability = capability_read(selected, catalog_provider)
    return read, catalog_provider
