"""The last verified registry, kept in the data folder so the list stays shown offline."""

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from shared.config import get_storage_settings

LIST = "plugins.json"
SIGNATURE = "plugins.json.sig"
FETCHED_AT = "fetched_at"


@dataclass(frozen=True)
class CachedRegistry:
    body: bytes
    signature: bytes
    fetched_at: datetime


def cache_dir() -> Path:
    return get_storage_settings().plugin_registry_dir


def read_cached() -> CachedRegistry | None:
    folder = cache_dir()
    try:
        return CachedRegistry(
            body=(folder / LIST).read_bytes(),
            signature=(folder / SIGNATURE).read_bytes(),
            fetched_at=datetime.fromisoformat((folder / FETCHED_AT).read_text()),
        )
    except (OSError, ValueError):
        return None


def write_cached(body: bytes, signature: bytes) -> CachedRegistry:
    """The date is written last, so a copy cut short reads as no copy at all."""
    folder = cache_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / FETCHED_AT).unlink(missing_ok=True)
    _replace(folder / LIST, body)
    _replace(folder / SIGNATURE, signature)
    fetched_at = datetime.now(UTC)
    _replace(folder / FETCHED_AT, fetched_at.isoformat().encode())
    return CachedRegistry(body, signature, fetched_at)


def touch_cached(cached: CachedRegistry) -> CachedRegistry:
    """The same list fetched again: only its date moves."""
    fetched_at = datetime.now(UTC)
    _replace(cache_dir() / FETCHED_AT, fetched_at.isoformat().encode())
    return CachedRegistry(cached.body, cached.signature, fetched_at)


def _replace(path: Path, data: bytes) -> None:
    partial = path.with_name(f"{path.name}.partial")
    partial.write_bytes(data)
    os.replace(partial, path)
