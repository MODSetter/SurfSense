"""What a revised copy's version keeps in artifact_metadata: where it came from and what changed.

In metadata, not columns: ArtifactFileRole's CHECK constraint would need a
migration for the clean and external files, and ADR 0005 prefers metadata keys.
"""

from typing import Any, Literal

REVISION_KEY = "revision"

Action = Literal["edit", "accept_all", "reject_all"]
# The files beside the primary a Word version keeps, by their metadata key.
CLEAN = "clean"
EXTERNAL = "external"


def revision_of(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """The version's revision record, or None for any other artifact."""
    revision = (metadata or {}).get(REVISION_KEY)
    return revision if isinstance(revision, dict) else None


def pending_revision(
    *,
    derived_from_document_id: int | None,
    source_name: str,
    source_sha256: str | None,
    base_number: int | None,
    action: Action,
    operations: list[dict[str, Any]],
    internal_comment_ids: list[str],
) -> dict[str, Any]:
    """The record a version starts with; the job fills in the report, counts and files."""
    return {
        "derived_from_document_id": derived_from_document_id,
        "source_name": source_name,
        "source_sha256": source_sha256,
        "base_number": base_number,
        "action": action,
        "operations": operations,
        "report": None,
        "counts": None,
        "internal_comment_ids": internal_comment_ids,
        CLEAN: None,
        EXTERNAL: None,
    }


def change_count(revision: dict[str, Any]) -> int:
    """The tracked changes a Word version holds; 0 before its job counted them."""
    counts = revision.get("counts") or {}
    return int(counts.get("changes") or 0)
