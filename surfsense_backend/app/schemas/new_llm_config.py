"""
Pydantic schemas for the NewLLMConfig API.

NewLLMConfig combines LLM model settings with prompt configuration:
- LLM provider, model, API key, etc.
- Configurable system instructions
- Citation toggle
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db import LiteLLMProvider


class NewLLMConfigBase(BaseModel):
    """Base schema with common fields for NewLLMConfig."""

    name: str = Field(
        ..., max_length=100, description="User-friendly name for the configuration"
    )
    description: str | None = Field(
        None, max_length=500, description="Optional description"
    )

    # LLM Model Configuration
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

    # Prompt Configuration
    system_instructions: str = Field(
        default="",
        description="Custom system instructions. Empty string uses default SURFSENSE_SYSTEM_INSTRUCTIONS.",
    )
    use_default_system_instructions: bool = Field(
        default=True,
        description="Whether to use default instructions when system_instructions is empty",
    )
    citations_enabled: bool = Field(
        default=True,
        description="Whether to include citation instructions in the system prompt",
    )


class NewLLMConfigCreate(NewLLMConfigBase):
    """Schema for creating a new NewLLMConfig."""

    search_space_id: int = Field(
        ..., description="Search space ID to associate the config with"
    )


class NewLLMConfigUpdate(BaseModel):
    """Schema for updating an existing NewLLMConfig. All fields are optional."""

    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)

    # LLM Model Configuration
    provider: LiteLLMProvider | None = None
    custom_provider: str | None = Field(None, max_length=100)
    model_name: str | None = Field(None, max_length=100)
    api_key: str | None = None
    api_base: str | None = Field(None, max_length=500)
    litellm_params: dict[str, Any] | None = None

    # Prompt Configuration
    system_instructions: str | None = None
    use_default_system_instructions: bool | None = None
    citations_enabled: bool | None = None


class NewLLMConfigRead(NewLLMConfigBase):
    """Schema for reading a NewLLMConfig (includes id and timestamps)."""

    id: int
    created_at: datetime
    search_space_id: int

    model_config = ConfigDict(from_attributes=True)


class NewLLMConfigPublic(BaseModel):
    """
    Public schema for NewLLMConfig that hides the API key.
    Used when returning configs in list views or to users who shouldn't see keys.
    """

    id: int
    name: str
    description: str | None = None

    # LLM Model Configuration (no api_key)
    provider: LiteLLMProvider
    custom_provider: str | None = None
    model_name: str
    api_base: str | None = None
    litellm_params: dict[str, Any] | None = None

    # Prompt Configuration
    system_instructions: str
    use_default_system_instructions: bool
    citations_enabled: bool

    created_at: datetime
    search_space_id: int

    model_config = ConfigDict(from_attributes=True)


class DefaultSystemInstructionsResponse(BaseModel):
    """Response schema for getting default system instructions."""

    default_system_instructions: str = Field(
        ..., description="The default SURFSENSE_SYSTEM_INSTRUCTIONS template"
    )


class GlobalNewLLMConfigRead(BaseModel):
    """
    Schema for reading global LLM configs from YAML.
    Global configs have negative IDs and no search_space_id.
    API key is hidden for security.

    ID 0 is reserved for Auto mode which uses LiteLLM Router for load balancing.
    """

    id: int = Field(
        ...,
        description="Config ID: 0 for Auto mode, negative for global configs",
    )
    name: str
    description: str | None = None

    # LLM Model Configuration (no api_key)
    provider: str  # String because YAML doesn't enforce enum, "AUTO" for Auto mode
    custom_provider: str | None = None
    model_name: str
    api_base: str | None = None
    litellm_params: dict[str, Any] | None = None

    # Prompt Configuration
    system_instructions: str = ""
    use_default_system_instructions: bool = True
    citations_enabled: bool = True

    is_global: bool = True  # Always true for global configs
    is_auto_mode: bool = False  # True only for Auto mode (ID 0)


# =============================================================================
# LLM Preferences Schemas (for role assignments)
# =============================================================================


class LLMPreferencesRead(BaseModel):
    """Schema for reading LLM preferences (role assignments) for a search space."""

    agent_llm_id: int | None = Field(
        None, description="ID of the LLM config to use for agent/chat tasks"
    )
    document_summary_llm_id: int | None = Field(
        None, description="ID of the LLM config to use for document summarization"
    )
    agent_llm: dict[str, Any] | None = Field(
        None, description="Full config for agent LLM"
    )
    document_summary_llm: dict[str, Any] | None = Field(
        None, description="Full config for document summary LLM"
    )

    model_config = ConfigDict(from_attributes=True)


class LLMPreferencesUpdate(BaseModel):
    """Schema for updating LLM preferences."""

    agent_llm_id: int | None = Field(
        None, description="ID of the LLM config to use for agent/chat tasks"
    )
    document_summary_llm_id: int | None = Field(
        None, description="ID of the LLM config to use for document summarization"
    )
