"""Wire schemas spoken between the SurfSense Obsidian plugin and the backend.

All schemas inherit ``extra='ignore'`` from :class:`_PluginBase` so additive
field changes never break either side; hard breaks live behind a new URL
prefix (``/api/v2/...``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_PLUGIN_MODEL_CONFIG = ConfigDict(extra="ignore")


class _PluginBase(BaseModel):
    """Base schema carrying the shared forward-compatibility config."""

    model_config = _PLUGIN_MODEL_CONFIG


class NotePayload(_PluginBase):
    """One Obsidian note as pushed by the plugin (the source of truth)."""

    vault_id: str = Field(..., description="Stable plugin-generated UUID for this vault")
    path: str = Field(..., description="Vault-relative path, e.g. 'notes/foo.md'")
    name: str = Field(..., description="File stem (no extension)")
    extension: str = Field(default="md", description="File extension without leading dot")
    content: str = Field(default="", description="Raw markdown body (post-frontmatter)")

    frontmatter: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    headings: list[str] = Field(default_factory=list)
    resolved_links: list[str] = Field(default_factory=list)
    unresolved_links: list[str] = Field(default_factory=list)
    embeds: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)

    content_hash: str = Field(..., description="Plugin-computed SHA-256 of the raw content")
    mtime: datetime
    ctime: datetime


class SyncBatchRequest(_PluginBase):
    """Batch upsert; plugin sends 10-20 notes per request."""

    vault_id: str
    notes: list[NotePayload] = Field(default_factory=list, max_length=100)


class RenameItem(_PluginBase):
    old_path: str
    new_path: str


class RenameBatchRequest(_PluginBase):
    vault_id: str
    renames: list[RenameItem] = Field(default_factory=list, max_length=200)


class DeleteBatchRequest(_PluginBase):
    vault_id: str
    paths: list[str] = Field(default_factory=list, max_length=500)


class ManifestEntry(_PluginBase):
    hash: str
    mtime: datetime


class ManifestResponse(_PluginBase):
    """Path-keyed manifest of every non-deleted note for a vault."""

    vault_id: str
    items: dict[str, ManifestEntry] = Field(default_factory=dict)


class ConnectRequest(_PluginBase):
    """Vault registration / heartbeat. Replayed on every plugin onload."""

    vault_id: str
    vault_name: str
    search_space_id: int
    plugin_version: str
    device_id: str


class ConnectResponse(_PluginBase):
    """Carries the same handshake fields as ``HealthResponse`` so the plugin
    learns the contract without a separate ``GET /health`` round-trip."""

    connector_id: int
    vault_id: str
    search_space_id: int
    api_version: str
    capabilities: list[str]


class HealthResponse(_PluginBase):
    """API contract handshake. ``capabilities`` is additive-only string list."""

    api_version: str
    capabilities: list[str]
    server_time_utc: datetime
