"""Wire schemas spoken between the SurfSense Obsidian plugin and the backend.

All schemas inherit ``extra='ignore'`` from :class:`_PluginBase` so additive
field changes never break either side; hard breaks live behind a new URL
prefix (``/api/v2/...``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_PLUGIN_MODEL_CONFIG = ConfigDict(extra="ignore")


class _PluginBase(BaseModel):
    """Base schema carrying the shared forward-compatibility config."""

    model_config = _PLUGIN_MODEL_CONFIG


class NotePayload(_PluginBase):
    """One Obsidian note as pushed by the plugin (the source of truth)."""

    vault_id: str = Field(
        ..., description="Stable plugin-generated UUID for this vault"
    )
    path: str = Field(..., description="Vault-relative path, e.g. 'notes/foo.md'")
    name: str = Field(..., description="File stem (no extension)")
    extension: str = Field(
        default="md", description="File extension without leading dot"
    )
    content: str = Field(default="", description="Raw markdown body (post-frontmatter)")

    frontmatter: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    headings: list[str] = Field(default_factory=list)
    resolved_links: list[str] = Field(default_factory=list)
    unresolved_links: list[str] = Field(default_factory=list)
    embeds: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)

    content_hash: str = Field(
        ..., description="Plugin-computed SHA-256 of the raw content"
    )
    size: int | None = Field(
        default=None,
        ge=0,
        description="Byte size of the local file (mtime+size short-circuit signal). Optional for forward compatibility.",
    )
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
    size: int | None = Field(
        default=None,
        description="Byte size last seen by the server. Enables mtime+size short-circuit; absent when not yet recorded.",
    )


class ManifestResponse(_PluginBase):
    """Path-keyed manifest of every non-deleted note for a vault."""

    vault_id: str
    items: dict[str, ManifestEntry] = Field(default_factory=dict)


class ConnectRequest(_PluginBase):
    """Vault registration / heartbeat. Replayed on every plugin onload."""

    vault_id: str
    vault_name: str
    search_space_id: int
    vault_fingerprint: str = Field(
        ...,
        description=(
            "Deterministic SHA-256 over the sorted markdown paths in the vault "
            "(plus vault_name). Same vault content on any device produces the "
            "same value; the server uses it to dedup connectors across devices."
        ),
    )


class ConnectResponse(_PluginBase):
    """Carries the same handshake fields as ``HealthResponse`` so the plugin
    learns the contract without a separate ``GET /health`` round-trip."""

    connector_id: int
    vault_id: str
    search_space_id: int
    capabilities: list[str]


class HealthResponse(_PluginBase):
    """API contract handshake. ``capabilities`` is additive-only string list."""

    capabilities: list[str]
    server_time_utc: datetime


# Per-item batch ack schemas — wire shape is load-bearing for the plugin
# queue (see api-client.ts / sync-engine.ts:processBatch).


class SyncAckItem(_PluginBase):
    path: str
    status: Literal["ok", "error"]
    document_id: int | None = None
    error: str | None = None


class SyncAck(_PluginBase):
    vault_id: str
    indexed: int
    failed: int
    items: list[SyncAckItem] = Field(default_factory=list)


class RenameAckItem(_PluginBase):
    old_path: str
    new_path: str
    # ``missing`` is treated as success client-side (end state reached).
    status: Literal["ok", "error", "missing"]
    document_id: int | None = None
    error: str | None = None


class RenameAck(_PluginBase):
    vault_id: str
    renamed: int
    missing: int
    items: list[RenameAckItem] = Field(default_factory=list)


class DeleteAckItem(_PluginBase):
    path: str
    status: Literal["ok", "error", "missing"]
    error: str | None = None


class DeleteAck(_PluginBase):
    vault_id: str
    deleted: int
    missing: int
    items: list[DeleteAckItem] = Field(default_factory=list)


class StatsResponse(_PluginBase):
    """Backs the Obsidian connector tile in the web UI."""

    vault_id: str
    files_synced: int
    last_sync_at: datetime | None = None
