import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db import ConnectionScope, ModelSource


class ModelRead(BaseModel):
    id: int
    connection_id: int
    model_id: str
    display_name: str | None = None
    source: ModelSource | str
    supports_chat: bool | None = None
    max_input_tokens: int | None = None
    supports_image_input: bool | None = None
    supports_tools: bool | None = None
    supports_image_generation: bool | None = None
    capabilities_override: dict[str, Any] = Field(default_factory=dict)
    enabled: bool
    billing_tier: str | None = None
    catalog: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ConnectionRead(BaseModel):
    id: int
    provider: str
    base_url: str | None = None
    api_key: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    scope: ConnectionScope | str
    workspace_id: int | None = None
    user_id: uuid.UUID | None = None
    enabled: bool
    has_api_key: bool
    models: list[ModelRead] = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ModelSelection(BaseModel):
    model_id: str = Field(..., max_length=255)
    display_name: str | None = Field(None, max_length=255)
    source: ModelSource | str = ModelSource.DISCOVERED
    supports_chat: bool | None = None
    max_input_tokens: int | None = None
    supports_image_input: bool | None = None
    supports_tools: bool | None = None
    supports_image_generation: bool | None = None
    enabled: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelPreviewRead(BaseModel):
    model_id: str
    display_name: str | None = None
    source: ModelSource | str = ModelSource.DISCOVERED
    supports_chat: bool | None = None
    max_input_tokens: int | None = None
    supports_image_input: bool | None = None
    supports_tools: bool | None = None
    supports_image_generation: bool | None = None
    enabled: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectionCreate(BaseModel):
    provider: str = Field(..., max_length=100)
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    scope: ConnectionScope = ConnectionScope.SEARCH_SPACE
    workspace_id: int | None = None
    enabled: bool = True
    models: list[ModelSelection] = Field(default_factory=list)


class ModelTestPreview(ConnectionCreate):
    model_id: str = Field(..., max_length=255)


class ConnectionUpdate(BaseModel):
    provider: str | None = Field(None, max_length=100)
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = None
    extra: dict[str, Any] | None = None
    enabled: bool | None = None


class ModelCreate(BaseModel):
    """Manually register a model id on a connection.

    For providers without a usable ``/models`` endpoint (Perplexity, MiniMax,
    Azure deployments, etc.) or to pin a single model from a noisy provider.
    """

    model_id: str = Field(..., max_length=255)
    display_name: str | None = Field(None, max_length=255)


class ModelUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=255)
    enabled: bool | None = None
    supports_chat: bool | None = None
    max_input_tokens: int | None = None
    supports_image_input: bool | None = None
    supports_tools: bool | None = None
    supports_image_generation: bool | None = None
    capabilities_override: dict[str, Any] | None = None


class ModelsBulkUpdate(BaseModel):
    model_ids: list[int] = Field(..., min_length=1, max_length=1000)
    enabled: bool


class ModelProviderRead(BaseModel):
    provider: str
    transport: str
    discovery: str
    default_base_url: str | None = None
    base_url_required: bool
    auth_style: str
    local_only: bool = False


class VerifyConnectionResponse(BaseModel):
    status: str
    ok: bool
    message: str = ""


class ModelRolesRead(BaseModel):
    chat_model_id: int | None = 0
    vision_model_id: int | None = 0
    image_gen_model_id: int | None = 0


class ModelRolesUpdate(BaseModel):
    chat_model_id: int | None = None
    vision_model_id: int | None = None
    image_gen_model_id: int | None = None


class LlmSetupStatusRead(BaseModel):
    """Server-authoritative verdict for the per-workspace LLM onboarding gate.

    ``status`` is the only thing the frontend gate acts on; ``source`` is
    informational and ``can_configure`` selects the onboarding vs. blocked
    screen for members who cannot manage models.
    """

    status: Literal["ready", "needs_setup"]
    source: Literal["global_config", "models", "none"]
    can_configure: bool
