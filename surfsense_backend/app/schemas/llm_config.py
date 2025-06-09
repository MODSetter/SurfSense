from datetime import datetime
import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from .base import IDModel, TimestampModel
from app.db import LiteLLMProvider

class LLMConfigBase(BaseModel):
    name: str = Field(..., max_length=100, description="User-friendly name for the LLM configuration")
    provider: LiteLLMProvider = Field(..., description="LiteLLM provider type")
    custom_provider: Optional[str] = Field(None, max_length=100, description="Custom provider name when provider is CUSTOM")
    model_name: str = Field(..., max_length=100, description="Model name without provider prefix")
    api_key: str = Field(..., description="API key for the provider")
    api_base: Optional[str] = Field(None, max_length=500, description="Optional API base URL")
    litellm_params: Optional[Dict[str, Any]] = Field(default=None, description="Additional LiteLLM parameters")

class LLMConfigCreate(LLMConfigBase):
    pass

class LLMConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="User-friendly name for the LLM configuration")
    provider: Optional[LiteLLMProvider] = Field(None, description="LiteLLM provider type")
    custom_provider: Optional[str] = Field(None, max_length=100, description="Custom provider name when provider is CUSTOM")
    model_name: Optional[str] = Field(None, max_length=100, description="Model name without provider prefix")
    api_key: Optional[str] = Field(None, description="API key for the provider")
    api_base: Optional[str] = Field(None, max_length=500, description="Optional API base URL")
    litellm_params: Optional[Dict[str, Any]] = Field(None, description="Additional LiteLLM parameters")

class LLMConfigRead(LLMConfigBase, IDModel, TimestampModel):
    id: int
    created_at: datetime
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True) 