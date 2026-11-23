"""Chat models other apps downloaded on this computer: listed, picked, and the
switch for looking.

Every route reads this computer's folders and nothing else; none reaches the
network, so none asks about egress. Using a listed model is an install like any
other (`POST /llm/installs` with its `catalog_id`), which records it and loads it
where it lies.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from api.dependencies import SessionDep
from modules.llm.catalog.local.dependencies import LocalCatalogDep
from modules.llm.catalog.local.engines.llamacpp.elsewhere.looking import (
    PickRefusedError,
)
from modules.llm.catalog.local.router import row_read
from modules.llm.catalog.local.schemas import (
    ElsewhereRead,
    LookWrite,
    OfferedRead,
    PathWrite,
)
from modules.llm.catalog.local.service import LocalCatalogService
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel

router = APIRouter()


@router.get(
    "/catalog/local/elsewhere",
    response_model=ElsewhereRead,
    summary="Chat models other apps downloaded here",
)
def read_elsewhere(service: LocalCatalogDep, session: SessionDep) -> dict:
    """No network call of any kind: folder listings and GGUF headers."""
    return _view(service, _selected(session))


@router.put(
    "/catalog/local/elsewhere/look",
    response_model=ElsewhereRead,
    summary="Look in other apps' model folders, or stop",
)
def write_look(
    payload: LookWrite, service: LocalCatalogDep, session: SessionDep
) -> dict:
    service.elsewhere.set_look(payload.look)
    return _view(service, _selected(session))


@router.post(
    "/catalog/local/elsewhere/file",
    response_model=OfferedRead,
    summary="A GGUF file picked with the system's dialog, as a row to use",
)
def offer_file(
    payload: PathWrite, service: LocalCatalogDep, session: SessionDep
) -> dict:
    selected = _selected(session)
    try:
        row = service.offer_file(Path(payload.path), selected)
    except PickRefusedError as refused:
        raise _refusal(refused) from refused
    in_use = {selected: [ModelType.TEXT_GEN]} if selected else {}
    return {"row": row_read(row, in_use)}


@router.post(
    "/catalog/local/elsewhere/folders",
    response_model=ElsewhereRead,
    summary="Look in a folder of GGUF files from now on",
)
def add_folder(
    payload: PathWrite, service: LocalCatalogDep, session: SessionDep
) -> dict:
    try:
        service.elsewhere.add_folder(Path(payload.path))
    except PickRefusedError as refused:
        raise _refusal(refused) from refused
    return _view(service, _selected(session))


@router.delete(
    "/catalog/local/elsewhere/folders",
    response_model=ElsewhereRead,
    summary="Stop looking in a folder that was added; its files stay",
)
def remove_folder(
    payload: PathWrite, service: LocalCatalogDep, session: SessionDep
) -> dict:
    service.elsewhere.remove_folder(Path(payload.path))
    return _view(service, _selected(session))


def _view(service: LocalCatalogService, selected: str | None) -> dict:
    view = service.elsewhere_view(selected)
    inventory = service.inventory()
    budget = service.budget()
    in_use = {selected: [ModelType.TEXT_GEN]} if selected else {}
    return {
        "available": view.available,
        "look": view.look,
        "looked_in": [app.value for app in view.looked_in],
        "folders": list(view.folders),
        "rows": [row_read(row, in_use) for row in view.rows],
        "skipped": [
            {
                "app": skipped.app.value,
                "name": skipped.name,
                "path": str(skipped.path),
                "code": str(skipped.unusable.code),
                "reason": skipped.unusable.reason,
            }
            for skipped in view.skipped
        ],
        "budget": {
            "device_total_bytes": budget.device_total_bytes,
            "device_free_bytes": budget.device_free_bytes,
            "usable_vram_bytes": budget.usable_vram_bytes,
            "fit_reserve_bytes": budget.fit_reserve_bytes,
            "ram_available_bytes": budget.ram_available_bytes,
            "uma": budget.uma,
            "has_gpu": budget.has_gpu,
        },
        "gpu_status": inventory.gpu_status.value,
    }


def _selected(session: SessionDep) -> str | None:
    """The local chat model in use, so its row reads In use."""
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None or selected.connection_id is not None:
        return None
    return selected.name


def _refusal(refused: PickRefusedError) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        {"code": str(refused.unusable.code), "message": refused.unusable.reason},
    )
