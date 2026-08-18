"""One file part to attach when persisting an artifact."""

from __future__ import annotations

from dataclasses import dataclass

from app.artifacts.persistence.enums import ArtifactFileRole


@dataclass(frozen=True, slots=True)
class ArtifactFileInput:
    data: bytes
    filename: str
    mime_type: str
    role: ArtifactFileRole = ArtifactFileRole.PRIMARY
