"""Filesystem mode contracts and selection helpers for chat sessions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FilesystemMode(StrEnum):
    """Supported filesystem backends for agent tool execution."""

    CLOUD = "cloud"
    DESKTOP_LOCAL_FOLDER = "desktop_local_folder"


class ClientPlatform(StrEnum):
    """Client runtime reported by the caller."""

    WEB = "web"
    DESKTOP = "desktop"


@dataclass(slots=True)
class FilesystemSelection:
    """Resolved filesystem selection for a single chat request."""

    mode: FilesystemMode = FilesystemMode.CLOUD
    client_platform: ClientPlatform = ClientPlatform.WEB
    local_root_path: str | None = None

    @property
    def is_local_mode(self) -> bool:
        return self.mode == FilesystemMode.DESKTOP_LOCAL_FOLDER
