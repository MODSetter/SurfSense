"""OKF serializer/validator self-checks: emitted concepts stay conformant and the
frontmatter fields consumers rely on (type/title/timestamp) round-trip.
"""

from datetime import UTC, datetime

from app.db import Document, DocumentType
from app.services.okf import (
    ConceptRef,
    LogEntry,
    SubdirRef,
    document_to_concept,
    folder_to_index,
    folder_to_log,
    is_conformant_concept,
    parse_frontmatter,
    validate_concept,
)


def _make_document() -> Document:
    return Document(
        title="Weekly Sync Notes",
        document_type=DocumentType.NOTE,
        document_metadata={"tags": ["team", "meeting"], "url": "https://example.com/n"},
        updated_at=datetime(2026, 5, 28, 22, 49, 59, tzinfo=UTC),
    )


def test_concept_is_conformant_and_roundtrips() -> None:
    concept = document_to_concept(_make_document(), body="# Agenda\n\nShip OKF.")

    assert is_conformant_concept(concept)

    frontmatter, error = parse_frontmatter(concept)
    assert error is None
    assert frontmatter["type"] == "Note"
    assert frontmatter["title"] == "Weekly Sync Notes"
    assert frontmatter["tags"] == ["team", "meeting"]
    assert frontmatter["resource"] == "https://example.com/n"
    # timestamp must survive as an ISO-8601 string, not a parsed datetime.
    assert frontmatter["timestamp"] == "2026-05-28T22:49:59+00:00"
    assert "# Agenda" in concept


def test_type_is_always_present_even_without_metadata() -> None:
    doc = Document(title="Raw", document_type=DocumentType.CRAWLED_URL)
    concept = document_to_concept(doc, body="body")
    frontmatter, error = parse_frontmatter(concept)
    assert error is None
    assert frontmatter["type"] == "Web Page"
    # No source URL / tags available -> those recommended keys are omitted.
    assert "resource" not in frontmatter
    assert "tags" not in frontmatter


def test_validator_rejects_non_conformant_documents() -> None:
    assert validate_concept("no frontmatter here")
    assert validate_concept("---\ntitle: Missing type\n---\nbody")


def test_folder_index_groups_by_type_and_lists_subdirs() -> None:
    index = folder_to_index(
        concepts=[
            ConceptRef(title="Orders", filename="orders.md", type="Note", description="x"),
        ],
        subdirectories=[SubdirRef(name="tables", description="Table docs")],
    )
    assert "# Subdirectories" in index
    assert "* [tables](tables/index.md) - Table docs" in index
    assert "# Note" in index
    assert "* [Orders](orders.md) - x" in index


def test_folder_log_lists_concepts_newest_first() -> None:
    log = folder_to_log(
        [
            LogEntry(title="Older", timestamp="2026-01-01T00:00:00+00:00"),
            LogEntry(title="Newer", timestamp="2026-06-01T00:00:00+00:00"),
            LogEntry(title="Undated", timestamp=None),
        ]
    )
    assert "# Change Log" in log
    # Newest dated entry precedes the older one; undated sorts last.
    assert log.index("Newer") < log.index("Older") < log.index("Undated")
    assert "* Newer - 2026-06-01T00:00:00+00:00" in log


def test_folder_log_is_empty_when_no_entries() -> None:
    assert folder_to_log([]) == ""


def test_export_log_files_synthesized_only_where_docs_live() -> None:
    from app.services.export_service import _build_log_files

    files = dict(
        _build_log_files(
            {
                "": [LogEntry(title="Root Doc", timestamp="2026-05-01T00:00:00+00:00")],
                "Research/AI": [LogEntry(title="Nested", timestamp=None)],
            }
        )
    )
    assert "# Change Log" in files["log.md"]
    assert "Root Doc" in files["log.md"]
    assert "Nested" in files["Research/AI/log.md"]
    # No empty intermediate log: "Research" holds no concepts of its own.
    assert "Research/log.md" not in files


def test_export_index_files_include_root_version_and_ancestors() -> None:
    from app.services.export_service import _build_index_files

    # A concept nested two levels deep, with no direct docs in the middle dir.
    files = dict(
        _build_index_files(
            {
                "Research/AI": [
                    ConceptRef(title="Note", filename="note.md", type="Note")
                ]
            }
        )
    )

    # Root, the empty intermediate dir, and the leaf all get an index.md so the
    # hierarchy is fully navigable.
    assert files["index.md"].startswith('---\nokf_version: "0.1"\n---')
    assert "* [Research](Research/index.md)" in files["index.md"]
    assert "* [AI](AI/index.md)" in files["Research/index.md"]
    assert "* [Note](note.md)" in files["Research/AI/index.md"]
