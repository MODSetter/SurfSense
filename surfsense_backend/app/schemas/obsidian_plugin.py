"""
Obsidian Plugin connector schemas.

Wire format spoken between the SurfSense Obsidian plugin
(``surfsense_obsidian/``) and the FastAPI backend.

Stability contract
------------------
Every request and response schema sets ``model_config = ConfigDict(extra='ignore')``.
This is the API stability contract — not just hygiene:

- Old plugins talking to a newer backend silently drop any new response fields
  they don't understand instead of failing validation.
- New plugins talking to an older backend can include forward-looking request
  fields (e.g. attachments metadata) without the older backend rejecting them.

Hard breaking changes are reserved for the URL prefix (``/api/v2/...``).
Additive evolution is signaled via the ``capabilities`` array on
``HealthResponse`` / ``ConnectResponse`` — older plugins ignore unknown
capability strings safely.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_PLUGIN_MODEL_CONFIG = ConfigDict(extra="ignore")


class _PluginBase(BaseModel):
    """Base class for all plugin payload schemas.

    Carries the forward-compatibility config so subclasses don't have to
    repeat it.
    """

    model_config = _PLUGIN_MODEL_CONFIG


class NotePayload(_PluginBase):
    """One Obsidian note as pushed by the plugin.

    The plugin is the source of truth: ``content`` is the post-frontmatter
    body, ``frontmatter``/``tags``/``headings``/etc. are precomputed by the
    plugin via ``app.metadataCache`` so the backend doesn't have to re-parse.
    """

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
    """Batch upsert. Plugin sends 10-20 notes per request to amortize HTTP overhead."""

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
    """One row of the server-side manifest used by the plugin to reconcile."""

    hash: str
    mtime: datetime


class ManifestResponse(_PluginBase):
    """Path-keyed manifest of every non-deleted note for a vault."""

    vault_id: str
    items: dict[str, ManifestEntry] = Field(default_factory=dict)


class ConnectRequest(_PluginBase):
    """First-call handshake to register or look up a vault connector row."""

    vault_id: str
    vault_name: str
    search_space_id: int
    plugin_version: str
    device_id: str
    device_label: str | None = Field(
        default=None,
        description="User-friendly device name shown in the web UI (e.g. 'iPad Pro').",
    )


class ConnectResponse(_PluginBase):
    """Returned from POST /connect.

    Carries the same handshake fields as ``HealthResponse`` so the plugin
    learns the contract on its very first call without an extra round-trip
    to ``GET /health``.
    """

    connector_id: int
    vault_id: str
    search_space_id: int
    api_version: str
    capabilities: list[str]


class HealthResponse(_PluginBase):
    """API contract handshake.

    The plugin calls ``GET /health`` once per ``onload`` and caches the
    result. ``capabilities`` is a forward-extensible string list: future
    additions (``'pat_auth'``, ``'scoped_pat'``, ``'attachments_v2'``,
    ``'shared_search_spaces'``...) ship without breaking older plugins
    because they only enable extra behavior, never gate existing endpoints.
    """

    api_version: str
    capabilities: list[str]
    server_time_utc: datetime
