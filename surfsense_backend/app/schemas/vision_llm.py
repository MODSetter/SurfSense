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
    """Schema for reading global vision LLM configs from YAML.

    The ``billing_tier`` field allows the frontend to show a Premium/Free
    badge and (more importantly) tells the backend whether to debit the
    user's premium credit pool when this config is used. ``"free"`` is
    the default for backward compatibility — admins must explicitly opt
    a global config into ``"premium"``.
    """

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
    billing_tier: str = Field(
        default="free",
        description="'free' or 'premium'. Premium debits the user's premium credit pool (USD-cost-based).",
    )
    is_premium: bool = Field(
        default=False,
        description=(
            "Convenience boolean derived server-side from "
            "``billing_tier == 'premium'``. The new-chat model selector "
            "keys its Free/Premium badge off this field for parity with "
            "chat (`GlobalLLMConfigRead.is_premium`)."
        ),
    )
    quota_reserve_tokens: int | None = Field(
        default=None,
        description=(
            "Optional override for the per-call reservation in *tokens* — "
            "converted to micro-USD via the model's input/output prices at "
            "reservation time. Falls back to QUOTA_DEFAULT_RESERVE_TOKENS."
        ),
    )
    input_cost_per_token: float | None = Field(
        default=None,
        description=(
            "Optional input price in USD/token. Used by pricing_registration to "
            "register custom Azure / OpenRouter aliases with LiteLLM at startup."
        ),
    )
    output_cost_per_token: float | None = Field(
        default=None,
        description="Optional output price in USD/token. Pair with input_cost_per_token.",
    )
