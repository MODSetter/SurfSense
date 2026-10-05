"""Which version of which document an artifact is.

Kept in artifact_metadata rather than a table so dev_mod needs no migration;
03's artifact_versions table replaces it and its backfill reads these keys.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact


@dataclass(frozen=True)
class ArtifactVersion:
    root: int  # the artifact id of version 1
    number: int
    parent: int | None  # the version this one was made from

    def as_metadata(self) -> dict[str, Any]:
        return {"root": self.root, "number": self.number, "parent": self.parent}


def version_of(metadata: dict[str, Any] | None) -> ArtifactVersion | None:
    version = (metadata or {}).get("version")
    if not isinstance(version, dict):
        return None
    return ArtifactVersion(
        root=version["root"], number=version["number"], parent=version["parent"]
    )


def next_version_number(session: Session, workspace_id: int, root: int) -> int:
    """One past the root's newest version, so editing an old version adds a new one."""
    version = Artifact.artifact_metadata["version"]
    newest = session.scalar(
        select(func.max(version["number"].as_integer())).where(
            Artifact.workspace_id == workspace_id,
            version["root"].as_integer() == root,
        )
    )
    return (newest or 0) + 1
