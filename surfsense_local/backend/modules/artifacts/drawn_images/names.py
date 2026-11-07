"""A picture as a document asks for it: by name, `image-<artifact id>`.

An artifact is one version, so a name keeps meaning the same picture as edits are made.
"""

import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from modules.agent.thread_folder.layout import OUTPUTS
from modules.artifacts.drawn_images.as_png import as_png
from modules.artifacts.image_edits.editable import has_picture
from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.documents.models import DocumentStatus
from shared.config import get_storage_settings

_NAME = re.compile(r"image-([0-9]+)")
_BUSY = (DocumentStatus.PENDING, DocumentStatus.PROCESSING)


class ImageStillDrawingError(LookupError):
    """The name is right; the picture is not ready to place yet."""


def image_name(artifact_id: int) -> str:
    return f"image-{artifact_id}"


def is_image_name(name: str) -> bool:
    return _NAME.fullmatch(name) is not None


def image_file(
    session: Session, workspace_id: int, thread_id: int, thread_folder: Path, name: str
) -> Path:
    """The picture as a PNG in its chat's outputs, for the agent to open too.

    Written afresh from the kept file on every call: the agent can write to its
    outputs, and what a document places must be what the user's model drew.
    LookupError when this chat has no picture by that name to place.
    """
    match = _NAME.fullmatch(name)
    if match is None:
        raise LookupError(f"{name!r} is not a picture's name")
    artifact = session.get(Artifact, int(match[1]))
    if (
        artifact is None
        or artifact.workspace_id != workspace_id
        or artifact.chat_thread_id != thread_id
    ):
        raise LookupError(f"no picture {name} in this chat")
    if artifact.document.status in _BUSY:
        raise ImageStillDrawingError(f"{name} is still being drawn")
    if artifact.document.status is not DocumentStatus.READY or not has_picture(
        artifact
    ):
        raise LookupError(f"no picture {name} to place in this chat")
    primary = next(f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY)
    kept = get_storage_settings().data_dir / primary.storage_key
    try:
        png = as_png(kept.read_bytes(), primary.mime_type)
    except (OSError, ValueError) as error:
        raise LookupError(f"picture {name} cannot be read: {error}") from error
    copy = _copy_path(thread_folder, name)
    copy.parent.mkdir(parents=True, exist_ok=True)
    # Replaced whole: the API and the worker both write it, and a link on the path goes.
    written = copy.with_name(f"{copy.name}.{uuid.uuid4().hex[:8]}.tmp")
    written.write_bytes(png)
    written.replace(copy)
    return copy


def _copy_path(thread_folder: Path, name: str) -> Path:
    outputs = (thread_folder / OUTPUTS).resolve()
    copy = outputs / "images" / f"{name}.png"
    if not copy.parent.resolve().is_relative_to(outputs):
        raise LookupError(f"the folder for picture {name} leaves this chat's outputs")
    return copy
