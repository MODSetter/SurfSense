"""Backward-compatible shim.

The filesystem mode contracts moved to :mod:`app.agents.shared.filesystem_selection`
as part of promoting the shared agent toolkit out of ``new_chat`` into the
cross-agent kernel. Import from there directly; this re-export keeps the
not-yet-retired single-agent stack working during the migration and will be
removed with it.
"""

from __future__ import annotations

from app.agents.shared.filesystem_selection import (
    ClientPlatform,
    FilesystemMode,
    FilesystemSelection,
    LocalFilesystemMount,
)

__all__ = [
    "ClientPlatform",
    "FilesystemMode",
    "FilesystemSelection",
    "LocalFilesystemMount",
]
