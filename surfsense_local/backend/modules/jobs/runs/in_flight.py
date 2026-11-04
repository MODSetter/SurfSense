"""Whether a run of a pack is waiting or being worked out, in any workspace: the runner reads the
pack's files by path while it runs, so a newer version waits until it is done."""

from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.versions import IN_FLIGHT
from modules.documents.models import Document


def pack_in_use(session: Session, pack_id: str) -> bool:
    running = session.scalar(
        select(Artifact.id)
        .join(Document, Document.id == Artifact.document_id)
        .where(
            func.json_extract(Artifact.artifact_metadata, "$.job_run.pack_id")
            == pack_id,
            Document.status.in_(IN_FLIGHT),
        )
        .limit(1)
    )
    return running is not None


def version_in_use(session: Session, pack_id: str, jobs: Collection[str]) -> str | None:
    """The version of the pack a pending or processing run of one of its `jobs`, by key,
    reads: the one it started on. None while no run of them is."""
    return session.scalar(
        select(func.json_extract(Artifact.artifact_metadata, "$.job_run.pack_version"))
        .join(Document, Document.id == Artifact.document_id)
        .where(
            func.json_extract(Artifact.artifact_metadata, "$.job_run.pack_id")
            == pack_id,
            func.json_extract(Artifact.artifact_metadata, "$.job_run.job").in_(
                list(jobs)
            ),
            Document.status.in_(IN_FLIGHT),
        )
        .limit(1)
    )
