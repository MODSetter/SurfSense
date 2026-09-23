"""The committed remote manifest, read once per process."""

import logging
from functools import lru_cache
from pathlib import Path

from modules.llm.catalog.remote.manifest.lookup import RemoteLookup
from modules.llm.catalog.remote.manifest.schema import SCHEMA_VERSION, RemoteManifest

__all__ = ["load_remote_manifest", "remote_lookup"]

LOGGER = logging.getLogger(__name__)
MANIFEST = Path(__file__).with_name("models.json")


def load_remote_manifest(path: Path | None = None) -> RemoteManifest:
    return RemoteManifest.model_validate_json((path or MANIFEST).read_text())


@lru_cache
def remote_lookup() -> RemoteLookup:
    try:
        manifest = load_remote_manifest()
    except (OSError, ValueError) as error:
        # Losing the manifest costs labels, not function: every remote model
        # reads as unknown and stays selectable behind the test dialog.
        LOGGER.warning("remote model manifest unavailable: %s", error)
        manifest = RemoteManifest(
            schema_version=SCHEMA_VERSION, source="", refreshed_at="", providers={}
        )
    return RemoteLookup(manifest)
