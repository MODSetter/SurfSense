"""Pydantic schemas for image generation requests/results."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# ImageGeneration (request/result) Schemas
# =============================================================================


class ImageGenerationCreate(BaseModel):
    """Schema for creating an image generation request."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="A text description of the desired image(s)",
    )
    model: str | None = Field(
        None,
        max_length=200,
        description="The model to use (e.g., 'dall-e-3', 'gpt-image-1'). Overrides the config model.",
    )
    n: int | None = Field(
        None,
        ge=1,
        le=10,
        description="Number of images to generate (1-10).",
    )
    quality: str | None = Field(None, max_length=50)
    size: str | None = Field(None, max_length=50)
    style: str | None = Field(None, max_length=50)
    response_format: str | None = Field(None, max_length=50)
    workspace_id: int = Field(
        ..., description="Workspace ID to associate the generation with"
    )
    image_gen_model_id: int | None = Field(
        None,
        description=(
            "Image generation model ID. "
            "0 = Auto mode, negative = GLOBAL model, positive = BYOK Model row. "
            "If not provided, uses the workspace's image_gen_model_id preference."
        ),
    )


class ImageGenerationRead(BaseModel):
    """Schema for reading an image generation record."""

    id: int
    prompt: str
    model: str | None = None
    n: int | None = None
    quality: str | None = None
    size: str | None = None
    style: str | None = None
    response_format: str | None = None
    image_gen_model_id: int | None = None
    response_data: dict[str, Any] | None = None
    error_message: str | None = None
    workspace_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImageGenerationListRead(BaseModel):
    """Lightweight schema for listing image generations (without full response_data)."""

    id: int
    prompt: str
    model: str | None = None
    n: int | None = None
    quality: str | None = None
    size: str | None = None
    workspace_id: int
    created_at: datetime
    is_success: bool
    image_count: int | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_count(cls, obj: Any) -> "ImageGenerationListRead":
        """Create ImageGenerationListRead with computed fields."""
        image_count = None
        if obj.response_data and isinstance(obj.response_data, dict):
            data = obj.response_data.get("data")
            if isinstance(data, list):
                image_count = len(data)

        return cls(
            id=obj.id,
            prompt=obj.prompt,
            model=obj.model,
            n=obj.n,
            quality=obj.quality,
            size=obj.size,
            workspace_id=obj.workspace_id,
            created_at=obj.created_at,
            is_success=obj.response_data is not None,
            image_count=image_count,
        )
