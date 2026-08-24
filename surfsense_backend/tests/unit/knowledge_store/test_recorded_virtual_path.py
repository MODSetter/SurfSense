from types import SimpleNamespace

import pytest

from app.knowledge_store.paths import DOCUMENTS_ROOT, PATH_MARKER, recorded_virtual_path

pytestmark = pytest.mark.unit


def _doc(metadata=None, path=None):
    return SimpleNamespace(document_metadata=metadata, path=path)


def _recorded(doc):
    return recorded_virtual_path(doc.document_metadata, doc.path)


def test_marker_is_preferred():
    doc = _doc(
        metadata={PATH_MARKER: f"{DOCUMENTS_ROOT}/from-marker.md"},
        path=f"{DOCUMENTS_ROOT}/from-column.md",
    )
    assert _recorded(doc) == f"{DOCUMENTS_ROOT}/from-marker.md"


def test_column_is_the_fallback_when_marker_was_wiped():
    """A connector re-sync can drop the marker; the column must still pin the
    file so ingest overwrites in place instead of forking a duplicate."""
    doc = _doc(metadata={"md5_checksum": "x"}, path=f"{DOCUMENTS_ROOT}/kept.md")
    assert _recorded(doc) == f"{DOCUMENTS_ROOT}/kept.md"


def test_none_when_neither_names_a_store_path():
    assert _recorded(_doc()) is None
    assert _recorded(_doc(path="/elsewhere/x.md")) is None
