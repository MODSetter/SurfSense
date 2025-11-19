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
    created_at: datetime | None = Field(
        None, description="Creation timestamp (None for global configs)"
    )
    search_space_id: int | None = Field(
        None, description="Search space ID (None for global configs)"
    )

    model_config = ConfigDict(from_attributes=True)


class LLMConfigReadSafe(BaseModel):
    """Safe response schema that excludes sensitive API keys"""
    id: int
    name: str
    provider: LiteLLMProvider
    custom_provider: str | None = None
    model_name: str
    api_base: str | None = None
    litellm_params: dict[str, Any] | None = None
    language: str | None = None
    created_at: datetime | None = None
    search_space_id: int | None = None
    has_api_key: bool = Field(default=True, description="Indicates if API key is configured")

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_llm_config(cls, config) -> "LLMConfigReadSafe":
        """Create safe response from LLMConfig model"""
        return cls(
            id=config.id,
            name=config.name,
            provider=config.provider,
            custom_provider=config.custom_provider,
            model_name=config.model_name,
            api_base=config.api_base,
            litellm_params=config.litellm_params,
            language=config.language,
            created_at=config.created_at,
            search_space_id=config.search_space_id,
            has_api_key=bool(config.api_key),
        )
