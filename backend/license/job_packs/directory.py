"""A folder of `<id>-<version>.zip` files standing in for the releases: tests, local runs, emergencies.

A relative JOB_PACKS_DIR is taken from the working directory, /srv/remote in the image.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from license.job_packs.manifest import PackRefusedError
from license.job_packs.source import PackAsset, PackSourceError
from license.job_packs.verify import MAX_PACK_BYTES

logger = logging.getLogger(__name__)

# Digits 0 to 9 only: \d takes any script's, which no header can carry.
_ZIP_NAME = re.compile(r"^[a-z][a-z0-9-]{0,63}-[0-9]+\.[0-9]+\.[0-9]+\.zip$")


@dataclass(frozen=True)
class DirectorySource:
    folder: Path

    async def assets(self) -> list[PackAsset]:
        return await asyncio.to_thread(self._assets)

    async def read(self, asset: PackAsset) -> bytes:
        return await asyncio.to_thread(self._read, asset)

    def _assets(self) -> list[PackAsset]:
        if not self.folder.is_dir():
            raise PackSourceError(f"JOB_PACKS_DIR {self.folder} is not a folder")
        found = []
        try:
            entries = sorted(path for path in self.folder.iterdir() if path.is_file())
            for path in entries:
                if not _ZIP_NAME.fullmatch(path.name):
                    logger.warning(
                        "%s in JOB_PACKS_DIR is not named <id>-<version>.zip, "
                        "so it is skipped",
                        path.name,
                    )
                    continue
                stat = path.stat()
                found.append(
                    PackAsset(
                        name=path.name,
                        ref=f"dir:{path.name}:{stat.st_mtime_ns}:{stat.st_size}",
                        size=stat.st_size,
                        locator=str(path),
                    )
                )
        except OSError as error:
            raise PackSourceError(
                f"JOB_PACKS_DIR {self.folder} cannot be read ({type(error).__name__})"
            ) from error
        return found

    def _read(self, asset: PackAsset) -> bytes:
        if asset.size > MAX_PACK_BYTES:
            raise PackRefusedError(
                "PACK_TOO_LARGE", f"{asset.name} is larger than 50 MB."
            )
        try:
            # Bounded, in case the file grew after it was listed.
            with Path(asset.locator).open("rb") as zipped:
                data = zipped.read(MAX_PACK_BYTES + 1)
        except OSError as error:
            raise PackSourceError(
                f"{asset.name} cannot be read from JOB_PACKS_DIR ({type(error).__name__})"
            ) from error
        if len(data) > MAX_PACK_BYTES:
            raise PackRefusedError(
                "PACK_TOO_LARGE", f"{asset.name} is larger than 50 MB."
            )
        return data
