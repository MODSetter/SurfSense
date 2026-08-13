"""Normalized write payload for create/revise of any artifact kind."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.artifacts.persistence.enums import ArtifactFormat
from app.artifacts.schemas.file_input import ArtifactFileInput

__all__ = ["ArtifactFileInput", "ArtifactFormat", "ArtifactInput"]


@dataclass(frozen=True, slots=True)
class ArtifactInput:
    workspace_id: int
    title: str
    markdown_representation: str
    tool_call_id: str | None = None
    files: tuple[ArtifactFileInput, ...] = ()
    thread_id: int | None = None
    created_by_id: UUID | None = None
    format: ArtifactFormat | None = None
    artifact_id: int | None = None
    expected_generation: int | None = None
    metadata: dict[str, Any] | None = None
