"""Which versions the Edit box may change: a ready picture Studio drew or edited."""

from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.documents.models import DocumentStatus

EDITABLE_FORMATS = frozenset({"image", "infographic"})
# What an edit model reads as its reference; an SVG a remote model drew is not one.
RASTER_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})


def has_picture(artifact: Artifact) -> bool:
    return artifact.format in EDITABLE_FORMATS and any(
        file.role is ArtifactFileRole.PRIMARY and file.mime_type in RASTER_TYPES
        for file in artifact.files
    )


def image_editable(artifact: Artifact) -> bool:
    return artifact.document.status is DocumentStatus.READY and has_picture(artifact)
