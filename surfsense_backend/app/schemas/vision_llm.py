import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db import VisionProvider


class VisionLLMConfigBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=500)
    provider: VisionProvider = Field(...)
    custom_provider: str | None = Field(None, max_length=100)
    model_name: str = Field(..., max_length=100)
    api_key: str = Field(...)
    api_base: str | None = Field(None, max_length=500)
    api_version: str | None = Field(None, max_length=50)
    litellm_params: dict[str, Any] | None = Field(default=None)


class VisionLLMConfigCreate(VisionLLMConfigBase):
    search_space_id: int = Field(...)


class VisionLLMConfigUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)
    provider: VisionProvider | None = None
    custom_provider: str | None = Field(None, max_length=100)
    model_name: str | None = Field(None, max_length=100)
    api_key: str | None = None
    api_base: str | None = Field(None, max_length=500)
    api_version: str | None = Field(None, max_length=50)
    litellm_params: dict[str, Any] | None = None


class VisionLLMConfigRead(VisionLLMConfigBase):
    id: int
    created_at: datetime
    search_space_id: int
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class VisionLLMConfigPublic(BaseModel):
    id: int
    name: str
    description: str | None = None
    provider: VisionProvider
    custom_provider: str | None = None
    model_name: str
    api_base: str | None = None
    api_version: str | None = None
    litellm_params: dict[str, Any] | None = None
    created_at: datetime
    search_space_id: int
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class GlobalVisionLLMConfigRead(BaseModel):
    id: int = Field(...)
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
