"""Object-key construction for immutable artifact blobs."""

from __future__ import annotations

import os
import uuid

from app.artifacts.persistence import ArtifactFileRole


def build_artifact_file_key(
    *,
    workspace_id: int,
    artifact_id: int,
    role: ArtifactFileRole,
    filename: str,
) -> str:
    """Return ``artifacts/{workspace}/{artifact}/{role}/{uuid}{extension}``."""
    extension = os.path.splitext(filename)[1].lower()
    return (
        f"artifacts/{workspace_id}/{artifact_id}/{role.value}/"
        f"{uuid.uuid4().hex}{extension}"
    )
