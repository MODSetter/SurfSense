"""A real export bundle - concepts plus reserved ``index.md``/``log.md`` - must
pass the same ``validate_bundle`` a consumer would run.
"""

from datetime import UTC, datetime

from app.db import Document, DocumentType
from app.services.okf import (
    LogEntry,
    document_to_concept,
    folder_to_index,
    folder_to_log,
    validate_bundle,
)


def _sample_bundle() -> dict[str, str]:
    note = Document(
        title="Weekly Sync",
        document_type=DocumentType.NOTE,
        document_metadata={"tags": ["team"]},
        updated_at=datetime(2026, 5, 28, tzinfo=UTC),
    )
    page = Document(title="Docs Home", document_type=DocumentType.CRAWLED_URL)
    return {
        "weekly-sync.md": document_to_concept(note, body="# Agenda"),
        "docs-home.md": document_to_concept(page, body="content"),
        # Reserved files carry no frontmatter and must be exempt from the check.
        "index.md": folder_to_index(),
        "log.md": folder_to_log(
            [LogEntry(title="Weekly Sync", timestamp="2026-05-28T00:00:00+00:00")]
        ),
    }


def test_real_export_bundle_is_conformant() -> None:
    assert validate_bundle(_sample_bundle()) == {}


def test_audit_flags_a_drifted_concept() -> None:
    bundle = _sample_bundle()
    bundle["broken.md"] = "no frontmatter at all"
    problems = validate_bundle(bundle)
    assert list(problems) == ["broken.md"]
