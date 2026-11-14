"""Packs a developer names in SURFSENSE_LOCAL_JOB_PACKS, installed when the API starts.

This is how a dev build gets a developer's packs, beside the licence server's: folders or
.zip files, separated as PATH is. A pack that is refused is logged and the API starts.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import packs_dir
from modules.jobs.packs.manifest import PackRefusedError

logger = logging.getLogger(__name__)

DEV_PACKS = "SURFSENSE_LOCAL_JOB_PACKS"


def install_dev_packs() -> None:
    for entry in filter(None, os.environ.get(DEV_PACKS, "").split(os.pathsep)):
        source = Path(entry.strip())
        try:
            # A developer edits a pack without raising its version, so the edit replaces it.
            manifest = install_pack(source, packs_dir(), replace_same_version=True)
        except (PackRefusedError, OSError) as refused:
            logger.warning("job pack %s not installed: %s", source, refused)
            continue
        logger.info(
            "job pack %s %s installed from %s", manifest.id, manifest.version, source
        )
