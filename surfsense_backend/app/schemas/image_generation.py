"""
Pydantic schemas for Image Generation configs and generation requests.

ImageGenerationConfig: CRUD schemas for user-created image gen model configs.
ImageGeneration: Schemas for the actual image generation requests/results.
GlobalImageGenConfigRead: Schema for admin-configured YAML configs.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db import ImageGenProvider

# =============================================================================
# ImageGenerationConfig CRUD Schemas
# =============================================================================


class ImageGenerationConfigBase(BaseModel):
    """Base schema with fields for ImageGenerationConfig."""

    name: str = Field(
        ..., max_length=100, description="User-friendly name for the config"
    )
    description: str | None = Field(
        None, max_length=500, description="Optional description"
    )
    provider: ImageGenProvider = Field(
        ...,
        description="Image generation provider (OpenAI, Azure, Google AI Studio, Vertex AI, Bedrock, Recraft, OpenRouter, Xinference, Nscale)",
    )
    custom_provider: str | None = Field(
        None, max_length=100, description="Custom provider name"
    )
    model_name: str = Field(
        ..., max_length=100, description="Model name (e.g., dall-e-3, gpt-image-1)"
    )
    api_key: str = Field(..., description="API key for the provider")
    api_base: str | None = Field(
        None, max_length=500, description="Optional API base URL"
    )
    api_version: str | None = Field(
        None,
        max_length=50,
        description="Azure-specific API version (e.g., '2024-02-15-preview')",
    )
    litellm_params: dict[str, Any] | None = Field(
        default=None, description="Additional LiteLLM parameters"
    )


class ImageGenerationConfigCreate(ImageGenerationConfigBase):
    """Schema for creating a new ImageGenerationConfig."""

    search_space_id: int = Field(
        ..., description="Search space ID to associate the config with"
    )


class ImageGenerationConfigUpdate(BaseModel):
    """Schema for updating an existing ImageGenerationConfig. All fields optional."""

    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)
    provider: ImageGenProvider | None = None
    custom_provider: str | None = Field(None, max_length=100)
    model_name: str | None = Field(None, max_length=100)
    api_key: str | None = None
    api_base: str | None = Field(None, max_length=500)
    api_version: str | None = Field(None, max_length=50)
    litellm_params: dict[str, Any] | None = None


class ImageGenerationConfigRead(ImageGenerationConfigBase):
    """Schema for reading an ImageGenerationConfig (includes id and timestamps)."""

    id: int
    created_at: datetime
    search_space_id: int

    model_config = ConfigDict(from_attributes=True)


class ImageGenerationConfigPublic(BaseModel):
    """Public schema that hides the API key (for list views)."""

    id: int
    name: str
    description: str | None = None
    provider: ImageGenProvider
    custom_provider: str | None = None
    model_name: str
    api_base: str | None = None
    api_version: str | None = None
    litellm_params: dict[str, Any] | None = None
    created_at: datetime
    search_space_id: int

    model_config = ConfigDict(from_attributes=True)


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
    search_space_id: int = Field(
        ..., description="Search space ID to associate the generation with"
    )
    image_generation_config_id: int | None = Field(
        None,
        description=(
            "Image generation config ID. "
            "0 = Auto mode (router), negative = global YAML config, positive = DB config. "
            "If not provided, uses the search space's image_generation_config_id preference."
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
    image_generation_config_id: int | None = None
    response_data: dict[str, Any] | None = None
    error_message: str | None = None
    search_space_id: int
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
    search_space_id: int
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
            search_space_id=obj.search_space_id,
            created_at=obj.created_at,
            is_success=obj.response_data is not None,
            image_count=image_count,
        )


# =============================================================================
# Global Image Gen Config (from YAML)
# =============================================================================


class GlobalImageGenConfigRead(BaseModel):
    """
    Schema for reading global image generation configs from YAML.
    Global configs have negative IDs. API key is hidden.
    ID 0 is reserved for Auto mode (LiteLLM Router load balancing).
    """

    id: int = Field(
        ...,
        description="Config ID: 0 for Auto mode, negative for global configs",
    )
    name: str
    description: str | None = None
    provider: str
    custom_provider: str | None = None
    model_name: str
    api_base: str | None = None
    api_version: str | None = None
    litellm_params: dict[str, Any] | None = None
    is_global: bool = True
    is_auto_mode: bool = False
