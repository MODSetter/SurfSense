"""Result returned after a successful persist."""

from __future__ import annotations

from dataclasses import dataclass

from app.artifacts.persistence.enums import ArtifactFileRole


@dataclass(frozen=True, slots=True)
class ArtifactSavedFile:
    file_id: int
    role: ArtifactFileRole
    filename: str
    mime_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ArtifactSaved:
    status: str
    artifact_id: int
    version: int
    title: str
    path: str
    files: list[ArtifactSavedFile]
