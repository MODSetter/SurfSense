"""The packs the route may serve, read from the configured store at most once per TTL.

Each release is downloaded and checked once and kept in memory; one refused is
remembered and never fetched again, since a published asset never changes. A check
has its own deadline, past which the release is refused, so one slow zip holds back
no other. While the store fails, the last good packs stay served and the store is
read again in a minute. One read at a time, under a deadline, so a slow store holds
no request long.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from pathlib import Path

from license.job_packs.directory import DirectorySource
from license.job_packs.github_releases import GitHubReleases
from license.job_packs.manifest import PackRefusedError
from license.job_packs.source import PackSource, PackSourceError
from license.job_packs.verify import PublishedPack, verified_pack
from license.settings import config

logger = logging.getLogger(__name__)

RETRY_SECONDS = 60.0
READ_DEADLINE_SECONDS = 30.0
# A pack's few dozen files check in milliseconds. A zip still being checked after this
# is refused, so the read goes on to the other releases, and serves them.
CHECK_DEADLINE_SECONDS = 10.0


class PackSourceUnavailableError(RuntimeError):
    """No pack can be served: no store is set, or none has been read since the process started."""


def configured_source() -> PackSource | None:
    """JOB_PACKS_DIR when set, as the emergency path; else the repository, with its token."""
    if config.JOB_PACKS_DIR:
        return DirectorySource(Path(config.JOB_PACKS_DIR))
    if config.JOB_PACKS_GITHUB_REPO and config.JOB_PACKS_GITHUB_TOKEN:
        return GitHubReleases(
            config.JOB_PACKS_GITHUB_REPO, config.JOB_PACKS_GITHUB_TOKEN
        )
    return None


class PackCatalog:
    def __init__(
        self,
        source: PackSource | None,
        *,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.source = source
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = asyncio.Lock()
        self._packs: tuple[PublishedPack, ...] | None = None
        self._kept: dict[str, PublishedPack] = {}
        self._refused: set[str] = set()
        self._next_read = float("-inf")

    async def packs(self) -> tuple[PublishedPack, ...]:
        """Every pack that passed its checks, as of the last good read."""
        if self.source is None:
            raise PackSourceUnavailableError("No job pack store is set.")
        if self._clock() >= self._next_read:
            async with self._lock:
                # Another request may have read the store while this one waited.
                if self._clock() >= self._next_read:
                    await self._read(self.source)
        if self._packs is None:
            raise PackSourceUnavailableError(
                "The job pack store has not been read since the process started."
            )
        return self._packs

    async def _read(self, source: PackSource) -> None:
        try:
            async with asyncio.timeout(READ_DEADLINE_SECONDS):
                packs, partial = await self._read_store(source)
        except Exception as error:
            self._next_read = self._clock() + RETRY_SECONDS
            logger.error(
                "Job packs could not be read (%s), so %s until the store is read "
                "again in a minute",
                _described(error),
                "the last good packs are served"
                if self._packs is not None
                else "none is served",
                exc_info=not isinstance(error, PackSourceError | TimeoutError),
            )
            return
        self._packs = packs
        self._next_read = self._clock() + (RETRY_SECONDS if partial else self._ttl)

    async def _read_store(
        self, source: PackSource
    ) -> tuple[tuple[PublishedPack, ...], bool]:
        """The packs listed now, and whether a download failed and needs another try."""
        assets = await source.assets()
        packs: list[PublishedPack] = []
        partial = False
        for asset in assets:
            if asset.ref in self._kept:
                packs.append(self._kept[asset.ref])
                continue
            if asset.ref in self._refused:
                continue
            try:
                data = await source.read(asset)
                pack = await _checked(data, asset.name)
            except PackRefusedError as refused:
                logger.error(
                    "Job pack %s is refused, %s: %s",
                    asset.name,
                    refused.code,
                    refused.message,
                )
                self._refused.add(asset.ref)
            except PackSourceError as error:
                logger.warning(
                    "Job pack %s could not be downloaded, so it is tried again in a "
                    "minute: %s",
                    asset.name,
                    error,
                )
                partial = True
            except Exception as error:
                # A release that breaks the reader is refused like a bad one, so it
                # never takes the others down.
                logger.error(
                    "Job pack %s is refused: reading it failed (%s)",
                    asset.name,
                    type(error).__name__,
                )
                self._refused.add(asset.ref)
            else:
                self._kept[asset.ref] = pack
                packs.append(pack)
        listed = {asset.ref for asset in assets}
        self._kept = {ref: kept for ref, kept in self._kept.items() if ref in listed}
        self._refused &= listed
        return tuple(packs), partial


async def _checked(data: bytes, name: str) -> PublishedPack:
    """`verified_pack` in a thread, refused past CHECK_DEADLINE_SECONDS. A thread cannot be
    stopped, so it runs on to its end, but the read no longer waits for it."""
    try:
        async with asyncio.timeout(CHECK_DEADLINE_SECONDS):
            return await asyncio.to_thread(verified_pack, data, name=name)
    except TimeoutError:
        raise PackRefusedError(
            "NOT_A_PACK",
            f"{name} took over {CHECK_DEADLINE_SECONDS:g} s to check, as no pack does.",
        ) from None


def _described(error: Exception) -> str:
    if isinstance(error, PackSourceError):
        return str(error)
    if isinstance(error, TimeoutError):
        return f"the read took over {READ_DEADLINE_SECONDS:g} s"
    return type(error).__name__


_shared: PackCatalog | None = None


def shared_catalog() -> PackCatalog:
    """One catalog per process for the configured store, made again if the settings change."""
    global _shared
    source = configured_source()
    if _shared is None or _shared.source != source:
        _shared = PackCatalog(source, ttl_seconds=config.JOB_PACKS_CACHE_SECONDS)
        _announce(source)
    return _shared


def _announce(source: PackSource | None) -> None:
    """Which store is read, once per catalog; never the token."""
    if isinstance(source, DirectorySource):
        logger.info("Job packs are read from JOB_PACKS_DIR, %s", source.folder)
    elif isinstance(source, GitHubReleases):
        logger.info("Job packs are read from the releases of %s", source.repo)
    elif config.JOB_PACKS_GITHUB_REPO:
        logger.warning(
            "JOB_PACKS_GITHUB_REPO is set without JOB_PACKS_GITHUB_TOKEN, "
            "so no job pack is served"
        )
    else:
        logger.info(
            "No job pack store is set (JOB_PACKS_DIR, or JOB_PACKS_GITHUB_REPO with "
            "JOB_PACKS_GITHUB_TOKEN), so no job pack is served"
        )
