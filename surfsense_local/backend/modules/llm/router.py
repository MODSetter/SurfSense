from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm.activity import ModelBusyError, model_activity, model_key
from modules.llm.catalog.local.dependencies import LocalCatalogDep
from modules.llm.catalog.local.router import router as local_catalog_router
from modules.llm.catalog.remote.router import router as remote_catalog_router
from modules.llm.connections.router import router as connections_router
from modules.llm.dependencies import ProviderDep
from modules.llm.model_type import ModelType
from modules.llm.models import OnboardingCompletion, SelectedModel
from modules.llm.providers import get_provider, llamacpp, provider_names
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.residency import warm_selected
from modules.llm.schemas import (
    LocalImageRuntimeRead,
    ModelDeleteRead,
    ModelRead,
    OnboardingStatusRead,
    ProviderRead,
    SelectionRead,
    SelectionWrite,
)
from modules.llm.selectable import selectable_for
from modules.llm.selection import choose_model, complete_onboarding
from shared.config import get_llm_settings

router = APIRouter(prefix="/llm", tags=["llm"])
router.include_router(local_catalog_router)
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
            types=list(model.types),
            selectable_for=selectable_for(model.types, model.known),
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
    service: LocalCatalogDep,
    session: SessionDep,
) -> ModelDeleteRead:
    # Inventory from disk, not from the runtime. Asking the router first meant a
    # dead router made models undeletable, which is backwards: one reason to
    # delete a model is that things are broken, and removing a file needs
    # nothing running.
    engine = service.engine_holding(model_name)
    if engine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"model not found: {model_name}")
    if engine.bundled(model_name):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{model_name} comes with SurfSense and cannot be deleted",
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
        except ModelBusyError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
        except FileNotFoundError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"model not found: {model_name}"
            ) from error
    finally:
        install_lock.release()

    selection_cleared = await transact(
        session,
        _clear_selection,
        engine.provider,
        model_name,
        engine.model_type,
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
    chosen = _chosen_image_model(session)
    image = (
        service.sdcpp.installed_image(chosen.name)
        if chosen is not None and chosen.provider == sdcpp.PROVIDER
        else None
    )
    if image is None:
        return LocalImageRuntimeRead(file=None, args=[])
    return LocalImageRuntimeRead(file=image.file, args=list(image.args))


def _chosen_image_model(session: Session) -> SelectedModel | None:
    return session.get(SelectedModel, ModelType.IMAGE_GEN)


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
