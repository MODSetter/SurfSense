from types import SimpleNamespace

import pytest

from app.knowledge_store.paths import DOCUMENTS_ROOT, PATH_MARKER, recorded_virtual_path

pytestmark = pytest.mark.unit


def _doc(metadata=None, path=None):
    return SimpleNamespace(document_metadata=metadata, path=path)


def _recorded(doc):
    return recorded_virtual_path(doc.document_metadata, doc.path)


def test_column_is_preferred():
    """The durable column is what writers set; the marker is legacy and can go
    stale once writers stop stamping it, so the column wins when both are set."""
    doc = _doc(
        metadata={PATH_MARKER: f"{DOCUMENTS_ROOT}/stale-marker.md"},
        path=f"{DOCUMENTS_ROOT}/from-column.md",
    )
    assert _recorded(doc) == f"{DOCUMENTS_ROOT}/from-column.md"


def test_marker_is_the_fallback_until_the_column_is_backfilled():
    """A legacy row carries the path only on its marker until 189 fills the
    column; resolution must still find it in the meantime."""
    doc = _doc(metadata={PATH_MARKER: f"{DOCUMENTS_ROOT}/legacy.md"}, path=None)
    assert _recorded(doc) == f"{DOCUMENTS_ROOT}/legacy.md"


def test_none_when_neither_names_a_store_path():
    assert _recorded(_doc()) is None
    assert _recorded(_doc(path="/elsewhere/x.md")) is None
