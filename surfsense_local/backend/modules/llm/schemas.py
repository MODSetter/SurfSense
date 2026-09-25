from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from modules.llm.connections.service import CapabilitySource
from modules.llm.model_type import ModelType
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
    types: list[ModelType] = []
    # The slots it can fill, by the one rule selection and every picker share.
    selectable_for: list[ModelType] = []


class ModelDeleteRead(BaseModel):
    name: str
    selection_cleared: bool


class ConnectionWrite(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    provider: str = "openai_compatible"
    base_url: str = Field(min_length=1, max_length=2048)
    api_key: str | None = Field(default=None, max_length=4096)
    allow_unverified: bool = False
    # A manifest provider id, or `custom` for an endpoint the manifest does not list.
    catalog_provider: str = Field(default="custom", min_length=1, max_length=100)


class ConnectionRead(BaseModel):
    id: int
    label: str
    provider: str
    base_url: str
    catalog_provider: str
    has_api_key: bool
    created_at: datetime
    updated_at: datetime


class ConnectionModelRead(BaseModel):
    connection_id: int
    connection_label: str
    name: str
    types: list[ModelType]
    capability_source: CapabilitySource
    # Decided here, never in the renderer, so every picker offers the same set.
    selectable_for: list[ModelType]


class RuntimeFileRead(BaseModel):
    """One file sd-server is started on, and the flag that names it."""

    flag: str
    # Inside the images folder, which Electron resolves.
    path: str


class LocalImageRuntimeRead(BaseModel):
    """What Electron should have sd-server running; no files for nothing."""

    files: list[RuntimeFileRead]
    args: list[str]


class ModelTestWrite(BaseModel):
    """Asks one model to do its job once, for either role."""

    model: str = Field(min_length=1, max_length=512)
    prompt: str | None = Field(default=None, max_length=2000)


class ChatTestRead(BaseModel):
    reply: str


class SelectionWrite(BaseModel):
    """The choice a client makes for a model type."""

    provider: str
    connection_id: int | None = None
    name: str
    allow_unlisted: bool = False


class SelectionRead(BaseModel):
    """The model currently chosen for a model type."""

    model_config = ConfigDict(from_attributes=True)

    model_type: ModelType
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
