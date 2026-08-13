"""Result returned after a successful persist."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArtifactSavedFile:
    file_id: int
    role: str
    filename: str
    mime_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ArtifactSaved:
    status: str
    artifact_id: int
    generation: int
    title: str
    files: list[ArtifactSavedFile]
