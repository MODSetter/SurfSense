"""The model screen's HTTP surface.

Two catalog endpoints, deliberately. Curated plus installed renders offline and
instantly; search needs `huggingface.co` and is paged. One response covering
both would either block on the network or return partial results behind a flag,
and that flag is the `scanned` flag this phase deletes.

`GET /llm/system`, `GET /llm/catalog` and `POST /llm/install` **replace** routes
that already exist at those paths. This is an in place reshape, not an addition.
"""

import json
import logging
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from api.dependencies import SessionDep, transact
from modules.egress import service as egress
from modules.llm.catalog.dependencies import CatalogServiceDep
from modules.llm.catalog.schemas import (
    CatalogRead,
    InstallRequest,
    RepoRead,
    SearchRead,
    SystemRead,
)
from modules.llm.models import ModelRole, SelectedModel
from modules.llm.schemas import SelectionRead
from modules.llm.selection import choose_model

router = APIRouter()
logger = logging.getLogger(__name__)

STALE_ID = "catalog id is stale or unknown; refresh the catalog"


@router.get("/system", response_model=SystemRead, summary="This machine's memory")
def read_system(service: CatalogServiceDep) -> dict:
    """No scan, no button, no network. The allocator's own view."""
    return {
        "budget": _budget(service.budget()),
        "devices": [
            {
                "name": device.name,
                "description": device.description,
                "kind": device.type.name.lower(),
                "total_bytes": device.total_bytes,
                "free_bytes": device.free_bytes,
            }
            for device in service.devices()
        ],
    }


@router.get("/catalog", response_model=CatalogRead, summary="Tested and installed models")
def read_catalog(service: CatalogServiceDep, session: SessionDep) -> dict:
    """Renders on first paint with no network call of any kind."""
    selected = _selected_local(session)
    catalog = service.catalog()
    return {
        "budget": _budget(catalog.budget),
        "curated": [
            _row(row, catalog, selected, service) for row in catalog.curated
        ],
        "installed": [
            {
                "model_id": row.model_id,
                "file": row.file,
                "size_bytes": row.size_bytes,
                "selected": row.model_id == selected,
            }
            for row in catalog.installed
        ],
        "recommended_model_id": catalog.recommended_model_id,
    }


@router.get("/search", response_model=SearchRead, summary="Search Hugging Face")
async def search(
    service: CatalogServiceDep, session: SessionDep, q: str = "", limit: int = 30
) -> dict:
    """Absent rather than degraded when egress is off. That is the airgapped
    product: curated, installed and a local .gguf import all still work."""
    await transact(session, egress.require, egress.MODEL_SEARCH)
    try:
        hits = await service.search(q, limit=limit)
    except httpx.HTTPError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "huggingface.co is unreachable"
        ) from error
    return {"results": [_hit(hit) for hit in hits]}


@router.get("/search/{repo:path}", response_model=RepoRead, summary="Builds in a repo")
async def read_repo(repo: str, service: CatalogServiceDep, session: SessionDep) -> dict:
    """Where the header read happens, so the trigger is opening a result rather
    than hovering or typing. The list level badge stays approximate until here."""
    await transact(session, egress.require, egress.MODEL_SEARCH)
    try:
        return await service.repo(repo)
    except httpx.HTTPError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "huggingface.co is unreachable"
        ) from error


@router.post("/install", summary="Download a model and optionally select it")
async def install(
    payload: InstallRequest,
    request: Request,
    service: CatalogServiceDep,
    session: SessionDep,
) -> StreamingResponse:
    plan = service.resolve_install(payload.catalog_id)
    if plan is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, STALE_ID)

    await transact(session, egress.require, egress.MODEL_DOWNLOAD)

    lock = service.install_lock()
    if lock.locked():
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a model is already being installed"
        )
    await lock.acquire()

    async def progress() -> AsyncIterator[bytes]:
        try:
            yield _event("starting", message="Preparing download")
            async for step in service.install(plan):
                yield _event(
                    "downloading",
                    message=step.status,
                    completed=step.completed,
                    total=step.total,
                )
            yield _event("verifying", message="Checking the model")
            # Rewrite the preset, then wait for the runtime to come back with
            # the model. The router only learns about it by restarting, and
            # reporting complete before then tells the user a model is ready
            # while a chat returns `model not found`.
            service.reprice()
            yield _event("preparing", message="Preparing the model runtime")
            servable = await service.wait_until_servable(plan.model_id)

            selection = None
            if payload.select:
                yield _event("selecting", message="Selecting model")
                with request.app.state.session_factory() as fresh:
                    chosen = await choose_model(
                        fresh, ModelRole.GENERATION, service.provider_name, plan.model_id
                    )
                    selection = SelectionRead.model_validate(chosen).model_dump(
                        mode="json"
                    )
            yield _event(
                "complete",
                message=(
                    "Model is ready"
                    if servable
                    else "Downloaded. It becomes available once the runtime restarts."
                ),
                selection=selection,
            )
        except Exception:
            logger.exception("model install failed")
            yield _event(
                "error",
                message="The model could not be installed. Retry the download.",
            )
        finally:
            lock.release()

    return StreamingResponse(progress(), media_type="application/x-ndjson")


def _selected_local(session: SessionDep) -> str | None:
    selected = session.get(SelectedModel, ModelRole.GENERATION)
    if selected is None or selected.connection_id is not None:
        return None
    return selected.name


def _budget(budget) -> dict:
    return {
        "device_total_bytes": budget.device_total_bytes,
        "device_free_bytes": budget.device_free_bytes,
        "usable_vram_bytes": budget.usable_vram_bytes,
        "fit_reserve_bytes": budget.fit_reserve_bytes,
        "ram_available_bytes": budget.ram_available_bytes,
        "uma": budget.uma,
        "has_gpu": budget.has_gpu,
    }


def _fit(fit) -> dict:
    return {
        "state": fit.state.value,
        "need_bytes": fit.need_bytes,
        "budget_bytes": fit.budget_bytes,
        "offload_fraction": fit.offload_fraction,
        "approximate": fit.approximate,
    }


def _row(row, catalog, selected: str | None, service) -> dict:
    """One curated row. Note the absent `rank`: it orders this list and selects
    the star, and the renderer never needs to know the number."""
    installed = {entry.model_id for entry in catalog.installed}
    model_id = row.variant.file.removesuffix(".gguf")
    return {
        "catalog_id": service.catalog_id(row),
        "model_id": row.model_id,
        "variant_model_id": model_id,
        "label": row.label,
        "family": row.family,
        "parameter_count": row.parameter_count,
        "quantization": row.variant.quantization,
        "size_bytes": row.variant.size_bytes,
        "context_length": 0,
        "fit": _fit(row.fit),
        "badge": {"verdict": row.badge.verdict, "reason": row.badge.reason},
        "capabilities": list(row.capabilities),
        "installed": model_id in installed,
        "selected": model_id == selected,
        "can_install": row.can_install,
        "recommended": row.model_id == catalog.recommended_model_id,
    }


def _hit(hit) -> dict:
    return {
        "repo": hit.repo,
        "downloads": hit.downloads,
        "likes": hit.likes,
        "license": hit.license,
        "gated": hit.gated,
        "quantized_from": hit.quantized_from,
        "last_modified": hit.last_modified,
    }


def _event(kind: str, **payload: object) -> bytes:
    return (json.dumps({"type": kind, **payload}) + "\n").encode()
