from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from modules.artifacts.models import Artifact, ArtifactFileRole
from modules.documents.models import DocumentStatus

Prompt = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class StudioJobCreate(BaseModel):
    """A request to generate one artifact from a workspace's documents."""

    format: str
    document_ids: list[int]
    prompt: Prompt | None = None
    options: dict | None = None


class FormatRead(BaseModel):
    """A format the picker offers, and whether it is usable right now."""

    key: str
    label: str
    requires_role: str | None
    available: bool
    unavailable_reason: str | None


class ArtifactFileRead(BaseModel):
    role: ArtifactFileRole
    mime_type: str
    size_bytes: int
    original_filename: str


class ArtifactRead(BaseModel):
    """An artifact and the state of its underlying ARTIFACT document."""

    id: int
    document_id: int
    format: str
    generation: int
    title: str
    status: DocumentStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, artifact: Artifact) -> "ArtifactRead":
        document = artifact.document
        return cls(
            id=artifact.id,
            document_id=artifact.document_id,
            format=artifact.format,
            generation=artifact.generation,
            title=document.title,
            status=document.status,
            error_message=document.error_message,
            created_at=artifact.created_at,
            updated_at=artifact.updated_at,
        )


class ArtifactDetail(ArtifactRead):
    """One artifact, its rendered body, and its stored files."""

    content: str | None
    files: list[ArtifactFileRead]

    @classmethod
    def of(cls, artifact: Artifact) -> "ArtifactDetail":
        base = ArtifactRead.of(artifact).model_dump()
        return cls(
            **base,
            content=artifact.document.content,
            files=[
                ArtifactFileRead(
                    role=file.role,
                    mime_type=file.mime_type,
                    size_bytes=file.size_bytes,
                    original_filename=file.original_filename,
                )
                for file in artifact.files
            ],
        )
