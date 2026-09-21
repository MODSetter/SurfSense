from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from modules.llm.connections.service import CapabilitySource
from modules.llm.models import ModelRole
from modules.llm.profile import Tier


class ProviderRead(BaseModel):
    """A configured provider, and what it can do right now."""

    name: str
    healthy: bool
    can_download: bool
    # BYO-key providers need a key before they answer; the UI shows a key field
    # when one is required and not yet set.
    requires_key: bool
    configured: bool


class ModelRead(BaseModel):
    """A model the provider already has on disk."""

    name: str
    installed: bool
    capabilities: list[str]
    display_name: str | None = None


class ModelDeleteRead(BaseModel):
    name: str
    selection_cleared: bool


class ConnectionWrite(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    provider: str = "openai_compatible"
    base_url: str = Field(min_length=1, max_length=2048)
    api_key: str | None = Field(default=None, max_length=4096)
    allow_unverified: bool = False


class ConnectionRead(BaseModel):
    id: int
    label: str
    provider: str
    base_url: str
    has_api_key: bool
    created_at: datetime
    updated_at: datetime


class ConnectionModelRead(BaseModel):
    connection_id: int
    connection_label: str
    name: str
    capabilities: list[str]
    capability_source: CapabilitySource


class LocalImageModelRead(BaseModel):
    name: str
    label: str
    detail: str
    size_bytes: int
    installed: bool
    selected: bool


class LocalImageCatalogRead(BaseModel):
    """What this build can generate locally, and which model holds the role."""

    provider: str
    offered: bool
    ready: bool
    models: list[LocalImageModelRead]


class LocalImageRuntimeRead(BaseModel):
    """What Electron should have sd-server running, or nulls for nothing."""

    file: str | None
    args: list[str]


class ModelTestWrite(BaseModel):
    """Asks one model to do its job once, for either role."""

    model: str = Field(min_length=1, max_length=512)
    prompt: str | None = Field(default=None, max_length=2000)


class ChatTestRead(BaseModel):
    reply: str


class SelectionWrite(BaseModel):
    """The choice a client makes for a role."""

    provider: str
    connection_id: int | None = None
    name: str
    allow_unlisted: bool = False


class SelectionRead(BaseModel):
    """The model currently answering for a role."""

    model_config = ConfigDict(from_attributes=True)

    role: ModelRole
    provider: str
    connection_id: int | None
    name: str
    tier: Tier
    updated_at: datetime


class OnboardingStatusRead(BaseModel):
    completed: bool


class InstallRequest(BaseModel):
    catalog_id: str = Field(min_length=1, max_length=128)
    select: bool = True
