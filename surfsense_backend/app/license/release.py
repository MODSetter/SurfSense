"""The desktop release license mail links to.

Kept in lockstep with ``surfsense_web/lib/app-release.ts``: both name the same
tag, and ``surfsense_local/scripts/bump-version.sh`` writes both. Resolving by
tag rather than ``/releases/latest`` keeps a mail that has already been sent
pointing at the build it was sent for.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Written by bump-version.sh. Do not edit by hand.
APP_RELEASE_VERSION = "2.0.1"
APP_RELEASE_TAG = f"v{APP_RELEASE_VERSION}"

_REPO = "MODSetter/SurfSense"
GITHUB_RELEASE_URL = f"https://github.com/{_REPO}/releases/tag/{APP_RELEASE_TAG}"

_API_URL = f"https://api.github.com/repos/{_REPO}/releases/tags/{APP_RELEASE_TAG}"
_INSTALLER = re.compile(r"\.(exe|dmg|AppImage|deb)$")
_TIMEOUT = 5.0
_CACHE_TTL = 3600.0


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    name: str
    url: str


# Same labels and suffix order as the /downloads grid.
_ASSET_LABELS: tuple[tuple[str, str], ...] = (
    (".exe", "Windows (exe)"),
    ("-arm64.dmg", "macOS Apple Silicon (dmg)"),
    ("-x64.dmg", "macOS Intel (dmg)"),
    (".deb", "Linux (deb)"),
    (".AppImage", "Linux (AppImage)"),
)

_lock = asyncio.Lock()
_cached_at = 0.0
_cached: tuple[ReleaseAsset, ...] = ()


def asset_label(name: str) -> str:
    for suffix, label in _ASSET_LABELS:
        if name.endswith(suffix):
            return label
    return name


def parse_assets(data: object) -> tuple[ReleaseAsset, ...]:
    """Installer files from a GitHub release payload, in the grid's order."""
    if not isinstance(data, dict):
        return ()
    raw = data.get("assets")
    if not isinstance(raw, list):
        return ()
    assets = [
        ReleaseAsset(name=item["name"], url=item["browser_download_url"])
        for item in raw
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
        and isinstance(item.get("browser_download_url"), str)
        and _INSTALLER.search(item["name"])
    ]
    rank = {suffix: index for index, (suffix, _) in enumerate(_ASSET_LABELS)}
    assets.sort(
        key=lambda asset: next(
            (rank[suffix] for suffix in rank if asset.name.endswith(suffix)),
            len(rank),
        )
    )
    return tuple(assets)


async def get_release_assets(
    *, client: httpx.AsyncClient | None = None
) -> tuple[ReleaseAsset, ...]:
    """Installers for ``APP_RELEASE_TAG``. Empty rather than raising.

    A passed ``client`` skips the cache, so tests do not share production hits.
    """
    if client is not None:
        return await _fetch(client)

    global _cached_at, _cached
    async with _lock:
        now = time.monotonic()
        if _cached_at and now - _cached_at < _CACHE_TTL:
            return _cached
        async with httpx.AsyncClient(timeout=_TIMEOUT) as owned:
            _cached = await _fetch(owned)
        _cached_at = time.monotonic()
        return _cached


async def _fetch(client: httpx.AsyncClient) -> tuple[ReleaseAsset, ...]:
    try:
        response = await client.get(
            _API_URL, headers={"Accept": "application/vnd.github+json"}
        )
        if response.status_code != 200:
            return ()
        return parse_assets(response.json())
    except (httpx.HTTPError, ValueError):
        logger.warning(
            "Could not load GitHub release %s for license mail", APP_RELEASE_TAG
        )
        return ()
