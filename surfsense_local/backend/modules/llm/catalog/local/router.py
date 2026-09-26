"""The local catalog's routes.

`/llm/catalog/local` renders offline and at once. Search is its own request,
egress gated, because what the user types goes to a third party. Opening a repo
reads its listing only; the one header read happens when a build is installed
(`install_jobs/`).
"""

from collections.abc import Mapping

import httpx
from fastapi import APIRouter, HTTPException, status

from api.dependencies import SessionDep, transact
from modules.egress import service as egress
from modules.llm.catalog.local.dependencies import LocalCatalogDep
from modules.llm.catalog.local.rows import BuildRow, LocalRow
from modules.llm.catalog.local.schemas import (
    LocalCatalogRead,
    RepoRead,
    SearchRead,
    SystemRead,
)
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.selectable import selectable_for

router = APIRouter()

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
    selected = {
        model_type: name
        for model_type in ModelType
        if (name := _selected_local(session, model_type))
    }
    catalog = service.catalog(selected)
    in_use: dict[str, list[ModelType]] = {}
    for model_type, name in selected.items():
        in_use.setdefault(name, []).append(model_type)
    return {
        "budget": _budget(catalog.budget),
        "gpu_status": catalog.gpu_status.value,
        "rows": [_row(row, in_use) for row in catalog.rows],
        "recommended_id": catalog.recommended_id,
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
        hits = await service.llamacpp.search(q, limit=limit)
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
    return {"repo": repo, "gated": gated, "row": _row(row, in_use={})}


def _selected_local(
    session: SessionDep, model_type: ModelType = ModelType.TEXT_GEN
) -> str | None:
    selected = session.get(SelectedModel, model_type)
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


def _row(row: LocalRow, in_use: Mapping[str, list[ModelType]]) -> dict:
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
        "builds": [_build(build, in_use) for build in row.builds],
        "default_quantization": row.default_quantization,
        "recommended": row.recommended,
        "engine": row.engine,
        "lead": (
            {"quantization": row.lead.quantization, "why": row.lead.why.value}
            if row.lead
            else None
        ),
        "voicing": (
            {
                "peak_mb": row.voicing.peak_mb,
                "voice_count": row.voicing.voice_count,
                "languages": list(row.voicing.languages),
            }
            if row.voicing
            else None
        ),
    }


def _build(build: BuildRow, in_use: Mapping[str, list[ModelType]]) -> dict:
    fit, badge = build.fit, build.badge
    return {
        "catalog_id": build.catalog_id,
        "quantization": build.build.quantization,
        "footprint_bytes": build.build.footprint_bytes,
        "download_bytes": build.download_bytes,
        "files": [
            {"role": f.role.value, "path": f.path, "size_bytes": f.size_bytes}
            for f in build.build.files
        ],
        "fit": (
            {
                "state": fit.state.value,
                "need_bytes": fit.need_bytes,
                "budget_bytes": fit.budget_bytes,
                "offload_fraction": fit.offload_fraction,
                "approximate": fit.approximate,
            }
            if fit
            else None
        ),
        "badge": (
            {
                "level": badge.level.value,
                "verdict": badge.verdict,
                "reason": badge.reason,
            }
            if badge
            else None
        ),
        "can_install": build.can_install,
        "installed_as": build.installed_as,
        "selected": build.installed_as is not None and build.installed_as in in_use,
        "selected_for": in_use.get(build.installed_as or "", []),
        "recommended": build.recommended,
        "reads_images": build.reads_images,
        "projector_checked": build.projector_checked,
        "bundled": build.bundled,
    }
