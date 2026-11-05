"""The version an edit starts from: its picture as stored, and what it says."""

from dataclasses import dataclass
from pathlib import PurePath

from sqlalchemy.orm import Session

from modules.artifacts.image_edits.recipe import ImageEdit
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.llm.providers.protocols import GeneratedImage
from shared.config import get_storage_settings


class BaseImageGoneError(RuntimeError):
    """The version this edit starts from, or its picture, is no longer there."""


@dataclass(frozen=True)
class BaseImage:
    title: str
    body: str
    picture: GeneratedImage
    # The base's file name without its extension, which the edit's format decides.
    stem: str


def base_image(session: Session, edit: ImageEdit) -> BaseImage:
    base = session.get(Artifact, edit.base_artifact_id)
    file = (
        next((f for f in base.files if f.role is ArtifactFileRole.PRIMARY), None)
        if base is not None
        else None
    )
    path = get_storage_settings().data_dir / file.storage_key if file else None
    if base is None or file is None or path is None or not path.is_file():
        raise BaseImageGoneError("The picture this version edits is gone.")
    return BaseImage(
        title=base.document.title,
        body=base.document.content or "",
        picture=GeneratedImage(path.read_bytes(), file.mime_type),
        stem=PurePath(file.original_filename).stem,
    )
