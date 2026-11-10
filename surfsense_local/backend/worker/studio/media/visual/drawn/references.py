"""The pictures a drawing keeps the characters and style of, read as stored."""

from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.llm.providers.protocols import GeneratedImage
from shared.config import get_storage_settings


class ReferenceGoneError(RuntimeError):
    """A picture this drawing keeps was deleted before it was drawn."""


def reference_pictures(
    session: Session, artifact_ids: tuple[int, ...]
) -> tuple[GeneratedImage, ...]:
    return tuple(_picture(session, artifact_id) for artifact_id in artifact_ids)


def _picture(session: Session, artifact_id: int) -> GeneratedImage:
    artifact = session.get(Artifact, artifact_id)
    file = (
        next((f for f in artifact.files if f.role is ArtifactFileRole.PRIMARY), None)
        if artifact is not None
        else None
    )
    path = get_storage_settings().data_dir / file.storage_key if file else None
    if file is None or path is None or not path.is_file():
        raise ReferenceGoneError(
            f"The picture image-{artifact_id} this one keeps is gone."
        )
    return GeneratedImage(path.read_bytes(), file.mime_type)
