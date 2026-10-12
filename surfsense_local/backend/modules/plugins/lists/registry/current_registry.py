"""The registry this app lists: the checkout's in development, else the last verified copy, refreshed."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from modules.plugins.lists.registry import registry_origin
from modules.plugins.lists.registry.registry_cache import (
    CachedRegistry,
    cache_dir,
    read_cached,
    touch_cached,
    write_cached,
)
from modules.plugins.lists.registry.registry_document import (
    RegistryDocument,
    UnreadableRegistryError,
    read_document,
)
from modules.plugins.lists.registry.registry_fetch import (
    RegistryFetchError,
    fetch_signed_list,
)
from modules.plugins.lists.registry.registry_icons import cache_icons
from modules.plugins.lists.registry.registry_keys import signed_by_registry
from modules.plugins.lists.registry.served_entry import served_entry

logger = logging.getLogger(__name__)

# As often as a plugin's tools are listed again before an agent turn.
REFRESH_EVERY = timedelta(minutes=5)
# A failed fetch waits as long as a good one, so an offline screen does not retry on each open.
_failed_at: dict[Path, datetime] = {}


@dataclass(frozen=True)
class CurrentRegistry:
    document: RegistryDocument
    fetched_at: datetime


def local_registry() -> CurrentRegistry | None:
    """No network: what the app would list now, or None when it holds no list at all."""
    if registry_origin.reads_repository():
        return _repository_registry()
    cached = read_cached()
    if cached is None:
        return None
    document = _verified(cached.body, cached.signature)
    return None if document is None else _current(document, cached.fetched_at)


async def refreshed_registry() -> CurrentRegistry | None:
    """The caller has checked that third-party plugins are on and the host allowed."""
    if registry_origin.reads_repository():
        return _repository_registry()
    cached = read_cached()
    if not _due(cached):
        return local_registry()
    folder = cache_dir()
    try:
        body, signature = await fetch_signed_list()
    except RegistryFetchError as error:
        logger.info("registry: fetch failed, keeping the cached copy: %s", error)
        _failed_at[folder] = datetime.now(UTC)
        return local_registry()
    fetched = _verified(body, signature)
    kept = local_registry()
    if fetched is None or _older(fetched, kept):
        _failed_at[folder] = datetime.now(UTC)
        return kept
    _failed_at.pop(folder, None)
    if cached is not None and cached.body == body:
        stored: CachedRegistry = touch_cached(cached)
    else:
        stored = write_cached(body, signature)
    await cache_icons(fetched.entries)
    return _current(fetched, stored.fetched_at)


def _due(cached: CachedRegistry | None) -> bool:
    now = datetime.now(UTC)
    failed = _failed_at.get(cache_dir())
    if failed is not None and now - failed < REFRESH_EVERY:
        return False
    return cached is None or now - cached.fetched_at >= REFRESH_EVERY


def _verified(body: bytes, signature: bytes) -> RegistryDocument | None:
    if not signed_by_registry(body, signature):
        logger.warning("registry: signature does not verify; ignored")
        return None
    try:
        return read_document(body)
    except UnreadableRegistryError as error:
        logger.warning("registry: ignored: %s", error)
        return None


def _older(fetched: RegistryDocument, kept: CurrentRegistry | None) -> bool:
    """An older list could bring back a delisted plugin, so it never replaces a newer one."""
    if kept is None or kept.document.generated_at is None:
        return False
    if (
        fetched.generated_at is None
        or fetched.generated_at < kept.document.generated_at
    ):
        logger.warning("registry: older than the cached copy; ignored")
        return True
    return False


def _repository_registry() -> CurrentRegistry | None:
    path = registry_origin.REPOSITORY_REGISTRY / "plugins.json"
    try:
        document = read_document(path.read_bytes())
    except (OSError, UnreadableRegistryError) as error:
        logger.info("registry: no list in the checkout: %s", error)
        return None
    return _current(document, datetime.fromtimestamp(path.stat().st_mtime, UTC))


def _current(document: RegistryDocument, fetched_at: datetime) -> CurrentRegistry:
    served = RegistryDocument(
        document.generated_at,
        [served_entry(entry) for entry in document.entries],
        document.removed,
    )
    return CurrentRegistry(served, fetched_at)
