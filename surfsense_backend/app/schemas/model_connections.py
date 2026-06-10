import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db import ConnectionProtocol, ConnectionScope, ModelSource


class ModelRead(BaseModel):
    id: int
    connection_id: int
    model_id: str
    display_name: str | None = None
    source: ModelSource | str
    capabilities: dict[str, Any]
    capabilities_declared: dict[str, Any] = Field(default_factory=dict)
    capabilities_verified: dict[str, Any] = Field(default_factory=dict)
    capabilities_override: dict[str, Any] = Field(default_factory=dict)
    embedding_dimension: int | None = None
    enabled: bool
    billing_tier: str | None = None
    catalog: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ConnectionRead(BaseModel):
    id: int
    protocol: ConnectionProtocol | str
    native_provider: str | None = None
    base_url: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    scope: ConnectionScope | str
    search_space_id: int | None = None
    user_id: uuid.UUID | None = None
    enabled: bool
    has_api_key: bool
    last_verified_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    models: list[ModelRead] = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ConnectionCreate(BaseModel):
    protocol: ConnectionProtocol
    native_provider: str | None = None
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    scope: ConnectionScope = ConnectionScope.SEARCH_SPACE
    search_space_id: int | None = None
    enabled: bool = True


class ConnectionUpdate(BaseModel):
    native_provider: str | None = None
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = None
    extra: dict[str, Any] | None = None
    enabled: bool | None = None


class ModelUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=255)
    enabled: bool | None = None
    capabilities_override: dict[str, Any] | None = None


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
