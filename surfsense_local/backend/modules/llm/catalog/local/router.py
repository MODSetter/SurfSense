"""The local catalog's routes.

`/llm/catalog/local` renders offline and at once. Search is its own request,
egress gated, because what the user types goes to a third party. Opening a repo
reads its listing only; the one header read happens when a build is installed.
"""

import json
import logging
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from api.dependencies import SessionDep, transact
from modules.egress import service as egress
from modules.llm.catalog.local.dependencies import LocalCatalogDep
from modules.llm.catalog.local.rows import BuildRow, LocalRow
from modules.llm.catalog.local.schemas import (
    InstallRequest,
    LocalCatalogRead,
    RepoRead,
    SearchRead,
    SystemRead,
)
from modules.llm.catalog.local.service import InstallRefusedError
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.schemas import SelectionRead
from modules.llm.selectable import selectable_for
from modules.llm.selection import choose_model

router = APIRouter()
logger = logging.getLogger(__name__)

STALE_ID = "catalog id is stale or unknown; refresh the catalog"
UNREACHABLE = "huggingface.co is unreachable"


@router.get("/system", response_model=SystemRead, summary="This machine's memory")
def read_system(service: LocalCatalogDep) -> dict:
    inventory = service.inventory()
    return {
        "budget": _budget(service.budget()),
        "gpu_status": inventory.gpu_status.value,
        "devices": [
            {
                "name": device.name,
                "description": device.description,
                "kind": device.type.name.lower(),
                "total_bytes": device.total_bytes,
                "free_bytes": device.free_bytes,
            }
            for device in inventory.devices
        ],
    }


@router.get(
    "/catalog/local",
    response_model=LocalCatalogRead,
    summary="Curated and downloaded models",
)
def read_local_catalog(service: LocalCatalogDep, session: SessionDep) -> dict:
    """No network call of any kind."""
    selected = _selected_local(session)
    catalog = service.catalog(selected=selected)
    return {
        "budget": _budget(catalog.budget),
        "gpu_status": catalog.gpu_status.value,
        "rows": [_row(row, selected) for row in catalog.local.rows],
        "recommended_id": catalog.local.recommended_id,
    }


@router.get(
    "/catalog/local/search", response_model=SearchRead, summary="Search Hugging Face"
)
async def search(
    service: LocalCatalogDep, session: SessionDep, q: str = "", limit: int = 30
) -> dict:
    """Absent rather than degraded when egress is off."""
    await transact(session, egress.require, egress.HUGGINGFACE)
    try:
        hits = await service.search(q, limit=limit)
    except httpx.HTTPError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNREACHABLE) from error
    return {
        "results": [
            {
                "repo": hit.repo,
                "downloads": hit.downloads,
                "likes": hit.likes,
                "license": hit.license,
                "gated": hit.gated,
                "quantized_from": hit.quantized_from,
                "last_modified": hit.last_modified,
                "reads_images": hit.reads_images,
            }
            for hit in hits
        ]
    }


@router.get(
    "/catalog/local/search/{repo:path}",
    response_model=RepoRead,
    summary="Builds in a repo",
)
async def read_repo(repo: str, service: LocalCatalogDep, session: SessionDep) -> dict:
    """The listing only: sizes, hashes and names. No file is read to draw it."""
    await transact(session, egress.require, egress.HUGGINGFACE)
    try:
        row, gated = await service.repo(repo)
    except httpx.HTTPError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNREACHABLE) from error
    return {"repo": repo, "gated": gated, "row": _row(row, selected=None)}


@router.post("/install", summary="Download a model and optionally select it")
async def install(
    payload: InstallRequest,
    request: Request,
    service: LocalCatalogDep,
    session: SessionDep,
) -> StreamingResponse:
    plan = service.resolve_install(payload.catalog_id)
    if plan is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, STALE_ID)

    await transact(session, egress.require, egress.HUGGINGFACE)

    lock = service.install_lock()
    if lock.locked():
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a model is already being installed"
        )
    await lock.acquire()

    async def progress() -> AsyncIterator[bytes]:
        try:
            yield _event("starting", message="Checking the model")
            try:
                checked = await service.check(plan)
            except InstallRefusedError as refused:
                yield _event("error", message=str(refused))
                return
            yield _event("starting", message="Preparing download")
            async for step in service.install(checked):
                yield _event(
                    "downloading",
                    message=step.status,
                    completed=step.completed,
                    total=step.total,
                )
            yield _event("verifying", message="Checking the model")
            # The router only learns about a model by restarting, and reporting
            # complete before then promises a model a chat cannot reach.
            service.reprice()
            yield _event("preparing", message="Preparing the model runtime")
            servable = await service.wait_until_servable(checked.model_id)
            # Listed is not loaded: warm it now, while the user is still looking
            # at the install, so the first question does not pay a cold load.
            if servable:
                async for step in service.warm_model(checked.model_id):
                    yield _event(
                        "preparing",
                        message=_loading_message(step.stage),
                        progress=step.value,
                    )
            selection = None
            if payload.select:
                yield _event("selecting", message="Selecting model")
                with request.app.state.session_factory() as fresh:
                    chosen = await choose_model(
                        fresh,
                        ModelType.TEXT_GEN,
                        service.provider_name,
                        checked.model_id,
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
                "error", message="The model could not be installed. Retry the download."
            )
        finally:
            lock.release()

    return StreamingResponse(progress(), media_type="application/x-ndjson")


def _selected_local(session: SessionDep) -> str | None:
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
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


def _row(row: LocalRow, selected: str | None) -> dict:
    classification = row.classification
    return {
        "id": row.id,
        "origin": row.origin.value,
        "name": row.name,
        "family": row.family,
        "types": list(classification.types),
        "known": classification.known,
        "approximate": classification.approximate,
        "selectable_for": selectable_for(classification.types, classification.known),
        "support": {
            "context": row.support.context,
            "reads_images": row.support.reads_images,
            "tools": row.support.tools,
            "reasoning": row.support.reasoning,
        },
        "runnable": row.runnable,
        "not_runnable_reason": row.not_runnable_reason,
        "builds": [_build(build, selected) for build in row.builds],
        "default_quantization": row.default_quantization,
        "recommended": row.recommended,
        "lead": (
            {"quantization": row.lead.quantization, "why": row.lead.why.value}
            if row.lead
            else None
        ),
    }


def _build(build: BuildRow, selected: str | None) -> dict:
    fit = build.fit
    return {
        "catalog_id": build.catalog_id,
        "quantization": build.build.quantization,
        "footprint_bytes": build.build.footprint_bytes,
        "files": [
            {"role": f.role.value, "path": f.path, "size_bytes": f.size_bytes}
            for f in build.build.files
        ],
        "fit": {
            "state": fit.state.value,
            "need_bytes": fit.need_bytes,
            "budget_bytes": fit.budget_bytes,
            "offload_fraction": fit.offload_fraction,
            "approximate": fit.approximate,
        },
        "badge": {
            "level": build.badge.level.value,
            "verdict": build.badge.verdict,
            "reason": build.badge.reason,
        },
        "can_install": build.can_install,
        "installed_as": build.installed_as,
        "selected": build.installed_as is not None and build.installed_as == selected,
        "recommended": build.recommended,
        "reads_images": build.reads_images,
        "projector_checked": build.projector_checked,
    }


def _event(kind: str, **payload: object) -> bytes:
    return (json.dumps({"type": kind, **payload}) + "\n").encode()


# The runtime names its load stages; these are what a person reads.
_LOADING_MESSAGES = {
    "text_model": "Loading the model",
    "mmproj_model": "Loading image support",
    "spec_model": "Loading the draft model",
}


def _loading_message(stage: str | None) -> str:
    return _LOADING_MESSAGES.get(stage or "", "Loading the model")
