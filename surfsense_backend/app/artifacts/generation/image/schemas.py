"""Request/response shapes for the image generation doors."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.artifacts.schemas.saved import ArtifactSaved


class ImageGenRequest(BaseModel):
    """Text-to-image request shared by the authenticated and public doors."""

    prompt: str = Field(..., min_length=1, max_length=4000)
    n: int = Field(default=1, ge=1, le=4)


class ImageFileOut(BaseModel):
    file_id: int
    role: str
    filename: str
    mime_type: str
    size_bytes: int
    content_url: str


class ImageGenResponse(BaseModel):
    """A persisted image artifact returned by the authenticated developer door."""

    artifact_id: int
    workspace_id: int
    title: str
    files: list[ImageFileOut]

    @classmethod
    def from_saved(cls, saved: ArtifactSaved, *, workspace_id: int) -> ImageGenResponse:
        return cls(
            artifact_id=saved.artifact_id,
            workspace_id=workspace_id,
            title=saved.title,
            files=[
                ImageFileOut(
                    file_id=f.file_id,
                    role=f.role,
                    filename=f.filename,
                    mime_type=f.mime_type,
                    size_bytes=f.size_bytes,
                    content_url=(
                        f"/api/v1/workspaces/{workspace_id}/artifacts/"
                        f"{saved.artifact_id}/files/{f.file_id}/content"
                    ),
                )
                for f in saved.files
            ],
        )
