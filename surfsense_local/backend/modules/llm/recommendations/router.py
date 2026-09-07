import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from api.dependencies import SessionDep
from modules.llm.models import ModelRole, SelectedModel
from modules.llm.recommendations.catalog import (
    InsufficientDiskError,
    UnknownCatalogIdError,
)
from modules.llm.recommendations.dependencies import CatalogServiceDep
from modules.llm.recommendations.protocols import PartialDownloadCleaner
from modules.llm.schemas import (
    InstallRequest,
    RecommendationCatalogRead,
    RecommendationSystemRead,
    SelectionRead,
)
from modules.llm.selection import choose_model

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/system", response_model=RecommendationSystemRead)
async def recommendation_system(service: CatalogServiceDep) -> dict:
    scan = await service.advisor_catalog()
    return {
        "hardware": scan.system,
        "llmfit_version": scan.llmfit_version,
        "estimates_available": bool(scan.models),
        "warnings": scan.warnings,
    }


@router.get("/catalog", response_model=RecommendationCatalogRead)
async def recommendation_catalog(
    service: CatalogServiceDep,
    session: SessionDep,
    refresh: bool = False,
):
    selected = session.get(SelectedModel, ModelRole.GENERATION)
    selected_key = (selected.provider, selected.name) if selected is not None else None
    return await service.catalog(selected=selected_key, refresh=refresh)


@router.post("/install", summary="Install and optionally select a catalog model")
async def install_model(
    payload: InstallRequest,
    request: Request,
    service: CatalogServiceDep,
) -> StreamingResponse:
    try:
        runtime, _model, plan = await service.preflight(payload.catalog_id)
    except UnknownCatalogIdError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "catalog id is stale or unknown; refresh the catalog",
        ) from error
    except InsufficientDiskError as error:
        raise HTTPException(
            status.HTTP_507_INSUFFICIENT_STORAGE,
            {
                "message": "insufficient disk space",
                "required": error.required,
                "available": error.available,
            },
        ) from error
    except RuntimeError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    lock = service.install_lock(runtime.name)
    if lock.locked():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{runtime.name} is already installing a model",
        )
    await lock.acquire()

    async def progress() -> AsyncIterator[bytes]:
        try:
            yield _event("starting", message="Preparing download")
            async for step in runtime.install(plan):
                yield _event(
                    "downloading",
                    message=step.status,
                    completed=step.completed,
                    total=step.total,
                )
            yield _event("verifying", message="Verifying installed model")
            installed = next(
                (
                    model
                    for model in await runtime.installed_models()
                    if model.model_name == plan.model_name
                ),
                None,
            )
            if installed is None or "completion" not in installed.capabilities:
                raise RuntimeError("runtime did not verify a generation model")
            if (
                plan.quantization is not None
                and installed.quantization is not None
                and installed.quantization.casefold() != plan.quantization.casefold()
            ):
                raise RuntimeError("runtime installed an unexpected quantization")

            selection = None
            if payload.select:
                yield _event("selecting", message="Selecting model")
                with request.app.state.session_factory() as session:
                    selection = await choose_model(
                        session,
                        ModelRole.GENERATION,
                        runtime.name,
                        plan.model_name,
                    )
                    session.commit()
                    selection = SelectionRead.model_validate(selection).model_dump(
                        mode="json"
                    )
            yield _event(
                "complete",
                message="Model is ready",
                selection=selection,
            )
        except asyncio.CancelledError:
            if isinstance(runtime, PartialDownloadCleaner):
                try:
                    await runtime.cleanup_partial_downloads()
                except OSError:
                    logger.exception("Could not remove cancelled model download")
            raise
        except Exception:
            yield _event(
                "error",
                message="The model could not be installed. Retry the download.",
            )
        finally:
            lock.release()

    return StreamingResponse(progress(), media_type="application/x-ndjson")


def _event(kind: str, **payload: object) -> bytes:
    return (json.dumps({"type": kind, **payload}) + "\n").encode()
