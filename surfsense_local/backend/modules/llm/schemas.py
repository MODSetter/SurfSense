from datetime import datetime

from pydantic import BaseModel, ConfigDict

from modules.llm.models import ModelRole


class ProviderRead(BaseModel):
    """A configured provider, and what it can do right now."""

    name: str
    healthy: bool
    can_download: bool


class ModelRead(BaseModel):
    """A model the provider already has on disk."""

    name: str
    installed: bool
    capabilities: list[str]


class CatalogEntryRead(BaseModel):
    """A model on offer to download, with its size."""

    name: str
    label: str
    size_gb: float
    installed: bool


class PullRequest(BaseModel):
    """The one model to fetch, by its provider name."""

    name: str


class SelectionWrite(BaseModel):
    """The choice a client makes for a role."""

    provider: str
    name: str


class SelectionRead(BaseModel):
    """The model currently answering for a role."""

    model_config = ConfigDict(from_attributes=True)

    role: ModelRole
    provider: str
    name: str
    updated_at: datetime
