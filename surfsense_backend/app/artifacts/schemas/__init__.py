"""Pure write/read value objects for artifacts."""

from __future__ import annotations

from app.artifacts.persistence.enums import ArtifactFileRole, ArtifactFormat
from app.artifacts.schemas.file_input import ArtifactFileInput
from app.artifacts.schemas.input import ArtifactInput
from app.artifacts.schemas.saved import ArtifactSaved, ArtifactSavedFile

__all__ = [
    "ArtifactFileInput",
    "ArtifactFileRole",
    "ArtifactFormat",
    "ArtifactInput",
    "ArtifactSaved",
    "ArtifactSavedFile",
]
