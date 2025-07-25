import uuid
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


class LLMConfigCreate(LLMConfigBase):
    pass


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
    litellm_params: dict[str, Any] | None = Field(
        None, description="Additional LiteLLM parameters"
    )


class LLMConfigRead(LLMConfigBase, IDModel, TimestampModel):
    id: int
    created_at: datetime
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
