from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db import LiteLLMProvider

from .base import IDModel, TimestampModel


class LLMConfigBase(BaseModel):
    name: str = Field(
        ..., max_length=100, description="User-friendly name for the LLM configuration"
    )
    provider: LiteLLMProvider = Field(..., description="LiteLLM provider type")
    custom_provider: str | None = Field(
        None, max_length=100, description="Custom provider name when provider is CUSTOM"
    )
    model_name: str = Field(
        ..., max_length=100, description="Model name without provider prefix"
    )
    api_key: str = Field(..., description="API key for the provider")
    api_base: str | None = Field(
        None, max_length=500, description="Optional API base URL"
    )
    litellm_params: dict[str, Any] | None = Field(
        default=None, description="Additional LiteLLM parameters"
    )
    language: str | None = Field(
        default="English", max_length=50, description="Language for the LLM"
    )


class LLMConfigCreate(LLMConfigBase):
    search_space_id: int = Field(
        ..., description="Search space ID to associate the LLM config with"
    )


class LLMConfigUpdate(BaseModel):
    name: str | None = Field(
        None, max_length=100, description="User-friendly name for the LLM configuration"
    )
    provider: LiteLLMProvider | None = Field(None, description="LiteLLM provider type")
    custom_provider: str | None = Field(
        None, max_length=100, description="Custom provider name when provider is CUSTOM"
    )
    model_name: str | None = Field(
        None, max_length=100, description="Model name without provider prefix"
    )
    api_key: str | None = Field(None, description="API key for the provider")
    api_base: str | None = Field(
        None, max_length=500, description="Optional API base URL"
    )
    language: str | None = Field(
        None, max_length=50, description="Language for the LLM"
    )
    litellm_params: dict[str, Any] | None = Field(
        None, description="Additional LiteLLM parameters"
    )


class LLMConfigRead(LLMConfigBase, IDModel, TimestampModel):
    id: int
    created_at: datetime
    search_space_id: int

    model_config = ConfigDict(from_attributes=True)
