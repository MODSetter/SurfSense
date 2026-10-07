"""Keep a made version's Word files beside its primary and record what it changed.

Runs after persist, which clears the artifact's folder: the clean and external
files go in the same folder, so deleting the artifact removes them too.
"""

import hashlib
from typing import Any

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.revision import CLEAN, EXTERNAL, REVISION_KEY
from shared.config import get_storage_settings
from worker.studio.revised_copy.pipeline import Made


def record(artifact: Artifact, made: Made) -> None:
    revision = dict((artifact.artifact_metadata or {})[REVISION_KEY])
    revision.update(
        report=made.report,
        counts=made.counts,
        internal_comment_ids=made.internal_comment_ids,
        **{
            CLEAN: _keep(artifact, "clean.docx", made.clean),
            EXTERNAL: _keep(artifact, "external.docx", made.external),
        },
    )
    artifact.artifact_metadata = {
        **(artifact.artifact_metadata or {}),
        REVISION_KEY: revision,
    }


def _keep(artifact: Artifact, name: str, data: bytes | None) -> dict[str, Any] | None:
    if data is None:
        return None
    storage = get_storage_settings()
    path = storage.artifact_dir(artifact.workspace_id, artifact.id) / name
    path.write_bytes(data)
    return {
        "storage_key": str(path.relative_to(storage.data_dir)),
        "size_bytes": len(data),
        "checksum_sha256": hashlib.sha256(data).hexdigest(),
    }
