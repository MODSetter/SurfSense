"""A registry entry: the shared schema, plus the fields only the registry carries."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from modules.plugins.lists.list_entry import ListEntry


class RegistryEntry(ListEntry):
    # Every registry entry says it; only the first-party list has none.
    verification: Literal["verified", "community"]
    # Older apps do not list the entry.
    min_app_version: str | None = None
    # Added by CI when it signs the list; an icon whose bytes differ is not shown.
    icon_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class RemovedEntry(BaseModel):
    """A plugin a maintainer delisted: its tools stop being offered, its connection stays."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str
    reason: str
