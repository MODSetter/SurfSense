"""The one model a picture goes to: the edit model when one is chosen, else the
image model when it takes pictures, else none and the picture is drawn from words."""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.pictures_in.kept import kept_takes_pictures
from modules.llm.providers.protocols import ImageEditor
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.resolution import ModelResolutionError, image_editor_for

PictureSource = Literal["edit_model", "image_model"]


@dataclass(frozen=True)
class PictureModel:
    source: PictureSource
    selection: SelectedModel
    editor: ImageEditor


def picture_model(session: Session) -> PictureModel | None:
    """None when no chosen model takes a picture in. Egress and a missing install
    raise ModelResolutionError, as resolving any model does."""
    chosen = session.get(SelectedModel, ModelType.IMAGE_EDIT)
    if chosen is not None:
        return PictureModel(
            "edit_model", chosen, image_editor_for(session, chosen).editor
        )
    image = session.get(SelectedModel, ModelType.IMAGE_GEN)
    if image is None or not _takes_pictures(image):
        return None
    return PictureModel("image_model", image, image_editor_for(session, image).editor)


def picture_source(session: Session) -> PictureSource | None:
    """The same answer without building a client: what the app shows."""
    try:
        found = picture_model(session)
    except ModelResolutionError:
        return None
    return None if found is None else found.source


def _takes_pictures(selected: SelectedModel) -> bool:
    if selected.provider == sdcpp.PROVIDER:
        installed = get_local_catalog().sdcpp.installed_image(selected.name)
        return installed is not None and ModelType.IMAGE_EDIT in installed.types
    return kept_takes_pictures(selected)
