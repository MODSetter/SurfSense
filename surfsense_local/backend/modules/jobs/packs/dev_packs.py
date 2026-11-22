"""Packs a developer names in SURFSENSE_LOCAL_JOB_PACKS, installed when the API starts.

This is how a dev build gets a developer's packs, beside the ones the app ships: folders or
.zip files, separated as PATH is. A pack that is refused is logged and the API starts.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from pathlib import Path

from modules.jobs.packs.install import Accept, install_pack
from modules.jobs.packs.installed import packs_dir
from modules.jobs.packs.manifest import PackRefusedError

logger = logging.getLogger(__name__)

DEV_PACKS = "SURFSENSE_LOCAL_JOB_PACKS"


def install_dev_packs() -> None:
    sources = [
        Path(entry.strip())
        for entry in filter(None, os.environ.get(DEV_PACKS, "").split(os.pathsep))
    ]
    # A developer edits a pack without raising its version, so the edit replaces it.
    install_at_start(sources, replace_same_version=True)


def install_at_start(
    sources: Iterable[Path],
    *,
    accept: Accept | None = None,
    replace_same_version: bool = False,
) -> None:
    """Each source installed in turn; a refused one is logged, and never stops the API."""
    for source in sources:
        try:
            manifest = install_pack(
                source,
                packs_dir(),
                accept=accept,
                replace_same_version=replace_same_version,
            )
        except (PackRefusedError, OSError) as refused:
            logger.warning("job pack %s not installed: %s", source, refused)
            continue
        logger.info(
            "job pack %s %s installed from %s", manifest.id, manifest.version, source
        )
