"""Every ``DocumentType`` must serialize to a concept a permissive OKF consumer
can read: parseable frontmatter with a non-empty ``type``. Covers all types plus
missing metadata, empty body, and non-ASCII titles.
"""

from datetime import UTC, datetime

import pytest

from app.db import Document, DocumentType
from app.services.okf import document_to_concept, is_conformant_concept
from app.services.okf.validator import (
    RECOMMENDED_FRONTMATTER_KEYS,
    REQUIRED_FRONTMATTER_KEYS,
)


@pytest.mark.parametrize("document_type", list(DocumentType))
def test_every_document_type_serializes_to_conformant_concept(
    document_type: DocumentType,
) -> None:
    doc = Document(
        title="Sample",
        document_type=document_type,
        document_metadata={"url": "https://example.com/x"},
        updated_at=datetime(2026, 5, 28, tzinfo=UTC),
    )
    assert is_conformant_concept(document_to_concept(doc, body="body"))


def test_conformant_without_metadata_or_body() -> None:
    doc = Document(title="Bare", document_type=DocumentType.NOTE)
    assert is_conformant_concept(document_to_concept(doc, body=""))


def test_conformant_with_non_ascii_title() -> None:
    doc = Document(title="日本語ノート", document_type=DocumentType.NOTE)
    concept = document_to_concept(doc, body="本文")
    assert is_conformant_concept(concept)
    assert "日本語ノート" in concept


def test_contract_marks_only_type_as_required() -> None:
    assert REQUIRED_FRONTMATTER_KEYS == ("type",)
    assert set(RECOMMENDED_FRONTMATTER_KEYS) == {
        "title",
        "description",
        "resource",
        "tags",
        "timestamp",
    }
