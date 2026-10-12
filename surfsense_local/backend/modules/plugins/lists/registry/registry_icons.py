"""Each entry's icon, downloaded beside the cached list once its bytes match the signed hash."""

import hashlib
import re
from pathlib import Path

import httpx

from modules.plugins.lists.registry import registry_origin
from modules.plugins.lists.registry.registry_cache import cache_dir
from modules.plugins.lists.registry.registry_entry import RegistryEntry
from modules.plugins.lists.registry.registry_fetch import TIMEOUT, fetch_icon

# A plain file name, so a listed name can never reach outside the icons folder.
_ICON_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}\.(svg|png)$")
CONTENT_TYPES = {"svg": "image/svg+xml", "png": "image/png"}


def icons_dir() -> Path:
    return (
        registry_origin.REPOSITORY_REGISTRY / "icons"
        if registry_origin.reads_repository()
        else cache_dir() / "icons"
    )


def icon_file(entry: RegistryEntry) -> Path | None:
    """In development the checkout's icon, unhashed; otherwise only a verified copy."""
    if entry.icon is None or not _ICON_NAME.match(entry.icon):
        return None
    path = icons_dir() / entry.icon
    if not path.is_file():
        return None
    if not registry_origin.reads_repository() and not _matches(
        path.read_bytes(), entry.icon_sha256
    ):
        return None
    return path


def content_type(path: Path) -> str:
    return CONTENT_TYPES[path.suffix.removeprefix(".")]


async def cache_icons(entries: list[RegistryEntry]) -> None:
    """A missing or mismatched icon is skipped: the screen shows a letter instead."""
    folder = icons_dir()
    folder.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for entry in entries:
            if entry.icon is None or entry.icon_sha256 is None:
                continue
            if not _ICON_NAME.match(entry.icon) or icon_file(entry) is not None:
                continue
            data = await fetch_icon(client, entry.icon)
            if data is not None and _matches(data, entry.icon_sha256):
                (folder / entry.icon).write_bytes(data)


def _matches(data: bytes, sha256: str | None) -> bool:
    return sha256 is not None and hashlib.sha256(data).hexdigest() == sha256
